"""Manifest schema and deck builder for completeness-gated presentations."""

from __future__ import annotations

import io
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pptx import Presentation as PresentationFactory
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.util import Inches

from deliverable_render.store import Store

if TYPE_CHECKING:
    from pptx.presentation import Presentation
    from pptx.slide import SlideLayout


class DeckBuildError(ValueError):
    """The deck manifest or store cannot satisfy the build contract."""


@dataclass(frozen=True)
class SlideSpec:
    """One slide entry in a deck manifest edition."""

    slide_id: str
    title: str
    layout: str
    source: str
    dropped_reason: str | None = None
    allow_empty: bool = False

    def __post_init__(self) -> None:
        if not self.slide_id.strip():
            raise DeckBuildError("slide_id must be a non-empty string")
        if self.dropped_reason is not None:
            if not self.dropped_reason.strip():
                raise DeckBuildError("dropped_reason must be non-empty when provided")
            return
        if not self.title.strip():
            raise DeckBuildError(f"slide {self.slide_id}: title must be a non-empty string")
        if not self.layout.strip():
            raise DeckBuildError(f"slide {self.slide_id}: layout must be a non-empty string")
        if not self.source.strip():
            raise DeckBuildError(f"slide {self.slide_id}: source must be a non-empty string")


def _require_string(value: object, field_name: str, slide_id: str) -> str:
    if not isinstance(value, str):
        raise DeckBuildError(f"slide {slide_id}: {field_name} must be a string")
    return value


def _require_bool(value: object, field_name: str, slide_id: str) -> bool:
    if not isinstance(value, bool):
        raise DeckBuildError(f"slide {slide_id}: {field_name} must be a boolean")
    return value


@dataclass(frozen=True)
class DeckManifest:
    """Ordered deck edition: slide identifiers, layouts, and store queries."""

    slides: tuple[SlideSpec, ...]

    def __post_init__(self) -> None:
        ids = [slide.slide_id for slide in self.slides]
        if len(ids) != len(set(ids)):
            raise DeckBuildError("Duplicate slide_id in manifest")

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> DeckManifest:
        raw_slides = data.get("slides")
        if not isinstance(raw_slides, list):
            raise DeckBuildError("manifest slides must be an array")
        slides: list[SlideSpec] = []
        for item in raw_slides:
            if not isinstance(item, Mapping):
                raise DeckBuildError("each slide entry must be an object")
            slide_id = _require_string(item.get("slide_id", ""), "slide_id", "<unknown>")
            dropped = item.get("dropped_reason")
            if dropped is not None and not isinstance(dropped, str):
                raise DeckBuildError(f"slide {slide_id}: dropped_reason must be a string")
            allow_empty = item.get("allow_empty", False)
            slides.append(
                SlideSpec(
                    slide_id=slide_id,
                    title=_require_string(item.get("title", ""), "title", slide_id),
                    layout=_require_string(item.get("layout", ""), "layout", slide_id),
                    source=_require_string(item.get("source", ""), "source", slide_id),
                    dropped_reason=dropped,
                    allow_empty=_require_bool(allow_empty, "allow_empty", slide_id),
                )
            )
        return cls(tuple(slides))

    def slide_ids(self) -> frozenset[str]:
        return frozenset(slide.slide_id for slide in self.slides)

    def by_id(self) -> Mapping[str, SlideSpec]:
        return {slide.slide_id: slide for slide in self.slides}


@dataclass(frozen=True)
class BuildSummary:
    """Four-count build report; zeros are explicit so a clean build is distinguishable."""

    slides_built: int
    slides_carried: int
    slides_dropped_with_reason: int
    slides_missing_source: int

    def as_dict(self) -> dict[str, int]:
        return {
            "slides_built": self.slides_built,
            "slides_carried": self.slides_carried,
            "slides_dropped_with_reason": self.slides_dropped_with_reason,
            "slides_missing_source": self.slides_missing_source,
        }


def enforce_completeness(prior: DeckManifest, current: DeckManifest) -> None:
    """Require every prior slide_id to have a successor or an explicit dropped_reason."""
    current_by_id = current.by_id()
    for prior_slide in prior.slides:
        current_slide = current_by_id.get(prior_slide.slide_id)
        if current_slide is None:
            raise DeckBuildError(
                f"slide_id {prior_slide.slide_id!r} from the prior edition has no successor "
                "and no dropped_reason"
            )


def _resolve_layout(presentation: Presentation, layout_name: str) -> SlideLayout:
    for layout in presentation.slide_layouts:
        if layout.name == layout_name:
            return layout
    available = ", ".join(sorted(layout.name for layout in presentation.slide_layouts))
    raise DeckBuildError(f"Unknown layout {layout_name!r}; available: {available}")


def _resolve_static_asset(template_dir: Path, asset_name: str) -> Path:
    if Path(asset_name).is_absolute() or ".." in Path(asset_name).parts:
        raise DeckBuildError(
            f"static asset {asset_name!r} must be a relative path within the template directory"
        )
    template_root = template_dir.resolve()
    asset_path = (template_root / asset_name).resolve()
    try:
        asset_path.relative_to(template_root)
    except ValueError:
        raise DeckBuildError(
            f"static asset {asset_name!r} resolves outside the template directory"
        ) from None
    return asset_path


def _query_store(store: Store, source: str, template_dir: Path) -> str | None:
    if source.startswith("record:"):
        record_id = source.removeprefix("record:")
        for record in store.records:
            if record.record_id == record_id:
                return record.text
        return None
    if source.startswith("static:"):
        asset_name = source.removeprefix("static:")
        asset_path = _resolve_static_asset(template_dir, asset_name)
        if asset_path.is_file():
            return asset_path.read_text(encoding="utf-8").strip()
        return None
    raise DeckBuildError(f"Unsupported source query {source!r}; use record:<id> or static:<file>")


def _load_template(template: Path | bytes) -> Presentation:
    if isinstance(template, bytes):
        return PresentationFactory(io.BytesIO(template))
    return PresentationFactory(str(template))


def _content_placeholder(slide: object) -> Any:
    placeholders = getattr(slide, "placeholders", None)
    if placeholders is None:
        return None
    for placeholder in placeholders:
        if not getattr(placeholder, "is_placeholder", False):
            continue
        if not hasattr(placeholder, "text"):
            continue
        placeholder_format = placeholder.placeholder_format
        if placeholder_format.type in (PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT):
            return placeholder
        if placeholder_format.idx != 0:
            return placeholder
    return None


def _set_slide_title(slide: object, title: str) -> None:
    shapes = getattr(slide, "shapes", None)
    if shapes is None:
        return
    title_shape = shapes.title
    if title_shape is not None:
        title_shape.text = title
        return
    if not title:
        return
    textbox = shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(1))
    textbox.text = title


def build_deck(
    template: Path | bytes,
    manifest: DeckManifest,
    store: Store,
    *,
    prior: DeckManifest | None = None,
    template_dir: Path | None = None,
) -> tuple[bytes, BuildSummary]:
    """Assemble a presentation from template layouts and store-backed slide content."""
    if prior is not None:
        enforce_completeness(prior, manifest)

    presentation = _load_template(template)
    if template_dir is not None:
        resolved_template_dir = template_dir
    elif isinstance(template, Path):
        resolved_template_dir = template.parent
    else:
        resolved_template_dir = Path(".")

    prior_ids = prior.slide_ids() if prior is not None else frozenset()
    slides_built = 0
    slides_carried = 0
    slides_dropped_with_reason = 0
    slides_missing_source = 0

    for slide in manifest.slides:
        if slide.dropped_reason is not None:
            slides_dropped_with_reason += 1
            continue

        content = _query_store(store, slide.source, resolved_template_dir)
        if content is None or not content.strip():
            if slide.allow_empty:
                slides_missing_source += 1
                content = ""
            else:
                raise DeckBuildError(
                    f"slide_id {slide.slide_id!r}: store query {slide.source!r} returned nothing"
                )

        layout = _resolve_layout(presentation, slide.layout)
        new_slide = presentation.slides.add_slide(layout)
        _set_slide_title(new_slide, slide.title)
        body_shape = _content_placeholder(new_slide)
        if body_shape is not None and hasattr(body_shape, "text"):
            body_shape.text = content
        elif content:
            textbox = new_slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(4))
            textbox.text = content

        slides_built += 1
        if slide.slide_id in prior_ids:
            slides_carried += 1

    buffer = io.BytesIO()
    presentation.save(buffer)
    summary = BuildSummary(
        slides_built=slides_built,
        slides_carried=slides_carried,
        slides_dropped_with_reason=slides_dropped_with_reason,
        slides_missing_source=slides_missing_source,
    )
    return buffer.getvalue(), summary
