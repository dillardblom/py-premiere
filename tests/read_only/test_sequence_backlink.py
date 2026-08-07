"""Sequence.project_item back-link."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere

FIXTURE = SAMPLES_DIR / "models" / "minimal" / "06_api.prproj"


def test_sequence_project_item() -> None:
    application = py_premiere.parse(FIXTURE)
    for sequence in application.project.sequences:
        item = sequence.project_item
        assert item is not None
        assert item.name == sequence.name
        assert item.is_sequence
        # The item's live sequence UID round-trips to this sequence.
        assert item._sequence_uid == sequence.sequence_id
