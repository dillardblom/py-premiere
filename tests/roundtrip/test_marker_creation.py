"""Marker creation: byte-fidelity round-trip and field parity."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"
_SECOND = 254016000000


def test_add_marker_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]  # Seq A, has 4 markers
    before = len(sequence.markers)

    marker = sequence.add_marker(
        "py-created",
        Time(3 * _SECOND),
        comments="hi",
        marker_type="Comment",
        duration=Time(_SECOND),
    )
    assert marker.name == "py-created"
    assert len(sequence.markers) == before + 1

    target = tmp_path / "with_marker.prproj"
    application.project.save(target)

    # Re-parse runs the byte-identity self-check; a bad layout raises here.
    fresh = parse_project_fresh(target)
    created = [m for m in fresh.project.sequences[0].markers if m.name == "py-created"]
    assert len(created) == 1
    assert created[0].comments == "hi"
    assert created[0].type == "Comment"
    assert created[0].start.ticks == 3 * _SECOND
    assert created[0].end.ticks == 4 * _SECOND
    assert created[0].guid


def test_add_marker_is_idempotent(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    application.project.sequences[0].add_marker("x", Time(_SECOND))
    first = tmp_path / "a.prproj"
    application.project.save(first)
    second = tmp_path / "b.prproj"
    parse_project_fresh(first).project.save(second)
    assert first.read_bytes() == second.read_bytes()


def test_add_first_marker_from_scratch(tmp_path) -> None:
    # Seq B has no marker collection; add_marker synthesizes MarkerOwner +
    # the Markers collection.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    seq_b = application.project.sequences[1]
    assert seq_b.markers == []
    seq_b.add_marker("first-ever", Time(_SECOND), comments="scratch")
    assert len(seq_b.markers) == 1

    target = tmp_path / "scratch.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    markers = fresh.project.sequences[1].markers
    assert [m.name for m in markers] == ["first-ever"]
    assert markers[0].comments == "scratch"


def test_add_marker_validates() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    with pytest.raises(ValueError):
        sequence.add_marker("bad", Time(_SECOND), marker_type="NotAType")
    with pytest.raises(TypeError):
        sequence.add_marker("bad", 12345)  # start must be a Time


def test_remove_marker_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    before = len(sequence.markers)
    sequence.remove_marker(next(m for m in sequence.markers if m.name == "web"))
    assert len(sequence.markers) == before - 1

    target = tmp_path / "removed.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    names = {m.name for m in fresh.project.sequences[0].markers}
    assert "web" not in names
    assert len(names) == before - 1


def test_add_then_remove_restores_original(tmp_path) -> None:
    # The create/delete mutations are exact inverses.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    marker = sequence.add_marker("temp", Time(_SECOND))
    sequence.remove_marker(marker)
    target = tmp_path / "restored.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "06_api.prproj").read_bytes()


def test_remove_foreign_marker_raises() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    seq_a, seq_b = application.project.sequences[:2]
    with pytest.raises(ValueError):
        seq_b.remove_marker(seq_a.markers[0])


def test_removing_the_last_marker_drops_the_collection(tmp_path) -> None:
    # ExtendScript's deleteMarker leaves a marker-free sequence with no
    # MarkerOwner at all (native ground truth), so the add/remove pair must
    # come back to the original bytes.
    source = MINIMAL / "06_api.prproj"
    application = py_premiere.parse(source)
    sequence = next(s for s in application.project.sequences if s.name == "Seq B")
    assert sequence.markers == []
    sequence.remove_marker(sequence.add_marker("tmp", Time(_SECOND)))
    assert sequence._element.find("MarkerOwner") is None

    target = tmp_path / "no_markers.prproj"
    application.project.save(target)
    assert target.read_bytes() == source.read_bytes()


def test_removing_one_of_many_markers_keeps_the_collection(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]  # Seq A, 4 markers
    sequence.remove_marker(sequence.markers[0])
    assert sequence._element.find("MarkerOwner") is not None
    target = tmp_path / "fewer.prproj"
    application.project.save(target)
    assert len(parse_project_fresh(target).project.sequences[0].markers) == 3
