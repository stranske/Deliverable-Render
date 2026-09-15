"""PowerPoint deck rendering with manifest-driven completeness gates."""

from deliverable_render.pptx.manifest import (
    BuildSummary,
    DeckBuildError,
    DeckManifest,
    SlideSpec,
    build_deck,
    enforce_completeness,
)

__all__ = [
    "BuildSummary",
    "DeckBuildError",
    "DeckManifest",
    "SlideSpec",
    "build_deck",
    "enforce_completeness",
]
