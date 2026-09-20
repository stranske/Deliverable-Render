"""Contract tests for the communication-synthesis store envelope."""

from deliverable_render.store.schema import (
    ARRAY_FIELDS,
    REQUIRED_TOP_LEVEL,
    CommunicationSynthesisStore,
)


def test_communication_synthesis_store_documents_required_top_level_fields():
    assert CommunicationSynthesisStore.__required_keys__ == frozenset(REQUIRED_TOP_LEVEL)
    assert CommunicationSynthesisStore.__optional_keys__ == frozenset()
    assert ARRAY_FIELDS == ("periods", "entries", "themes", "documents", "gaps")
