"""Communication-synthesis store shape and shared evidence contract.

This is separate from the renderer's existing Store/StructuredStore models.
The source format nests mentions inside entries and uses mentions[].q to
identify a period, not an entry. Optional explicit entry_id references are
checked when present; neither field is silently discarded.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

REQUIRED_TOP_LEVEL = ("fund", "periods", "entries", "themes", "documents", "gaps")
ARRAY_FIELDS = REQUIRED_TOP_LEVEL[1:]
MONETARY_FIELDS = frozenset(
    {"amount", "aum", "balance", "capital", "market_value", "peak", "price", "size", "value"}
)


def evidence_schema() -> dict[str, Any]:
    """Read the offline-packaged copy of the Workflows evidence-object/v1 schema."""
    resource = files(__package__).joinpath("evidence-object-v1.schema.json")
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))
