"""Manifest schema and deck builder for completeness-gated presentations."""

from __future__ import annotations

import io
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pptx import Presentation
from pptx.util import Inches

if TYPE_CHECKING:
    from deliverable_render.store import Store


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
            raise DeckBuildError(f"slide {self.slide_id}: title must be non-empty")
        if not self.layout.strip():
            raise DeckBuildError(f"slide {self.slide_id}: layout must be non-empty")
        if not self.source.strip():
            raise DeckBuildError(f"slide {self.slide_id}: source must be non-empty")


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
            dropped = item.get("dropped_reason")
            slides.append(
                SlideSpec(
                    slide_id=str(item.get("slide_id", "")),
                    title=str(item.get("title", "")),
                    layout=str(item.get("layout", "")),
                    source=str(item.get("source", "")),
                    dropped_reason=str(dropped) if dropped is not None else None,
                    allow_empty=bool(item.get("allow_empty", False)),
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


def _resolve_layout(presentation: Presentation, layout_name: str):
    for layout in presentation.slide_layouts:
        if layout.name == layout_name:
            return layout
    available = ", ".join(sorted(layout.name for layout in presentation.slide_layouts))
    raise DeckBuildError(f"Unknown layout {layout_name!r}; available: {available}")


def _query_store(store: Store, source: str, template_dir: Path) -> str | None:
    if source.startswith("record:"):
        record_id = source.removeprefix("record:")
        for record in store.records:
            if record.record_id == record_id:
                return record.text
        return None
    if source.startswith("static:"):
        asset_name = source.removeprefix("static:")
        asset_path = template_dir / asset_name
        if asset_path.is_file():
            return asset_path.read_text(encoding="utf-8").strip()
        return None
    raise DeckBuildError(f"Unsupported source query {source!r}; use record:<id> or static:<file>")


def _load_template(template: Path | bytes) -> Presentation:
    if isinstance(template, bytes):
        return Presentation(io.BytesIO(template))
    return Presentation(str(template))


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
    resolved_template_dir = template_dir or (
        Path(template) if isinstance(template, Path) else Path(".")
    )

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
        if new_slide.shapes.title is not None:
            new_slide.shapes.title.text = slide.title
        body_shape = new_slide.placeholders[1] if len(new_slide.placeholders) > 1 else None
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
