"""Clip (project-item) markers: read, create, delete."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"
FIXTURE = MINIMAL / "14_item_markers.prproj"  # wav item carries one marker


def _wav(application: py_premiere.models.Application) -> py_premiere.models.ProjectItem:
    return next(
        c for c in application.project.root_item.children if c.name == "renamed tone"
    )


def test_read_item_marker() -> None:
    application = py_premiere.parse(FIXTURE)
    markers = _wav(application).markers
    assert len(markers) == 1
    marker = markers[0]
    assert marker.name == "item marker"
    assert marker.comments == "from py-premiere probe"
    assert marker.start.seconds == 0.25
    assert marker.end.seconds == 0.75


def test_item_markers_are_not_sequence_markers() -> None:
    # The Seq A PANEL ITEM has its own (empty) collection, distinct from
    # the sequence's markers - matching UXP's view.
    application = py_premiere.parse(FIXTURE)
    seq_item = next(
        c for c in application.project.root_item.children if c.name == "Seq A"
    )
    assert seq_item.markers == []
    assert len(application.project.sequences[0].markers) == 4


def test_add_then_remove_item_marker_is_byte_identical(tmp_path) -> None:
    application = py_premiere.parse(FIXTURE)
    item = _wav(application)
    marker = item.add_marker("temp", Time(0), duration=Time(254016000000))
    item.remove_marker(marker)
    target = tmp_path / "inverse.prproj"
    application.project.save(target)
    assert target.read_bytes() == FIXTURE.read_bytes()


def test_add_item_marker_round_trips(tmp_path) -> None:
    application = py_premiere.parse(FIXTURE)
    _wav(application).add_marker(
        "second", Time(127008000000), comments="two", marker_type="Chapter"
    )
    target = tmp_path / "added.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    names = [m.name for m in _wav(fresh).markers]
    assert names == ["item marker", "second"]
    added = _wav(fresh).markers[1]
    assert added.type == "Chapter"
    assert added.comments == "two"


def test_strip_and_readd_matches_premiere(tmp_path) -> None:
    # Re-adding the marker Premiere itself added reproduces the exact bytes
    # once the random GUID (blob + pair) is normalized.
    application = py_premiere.parse(FIXTURE)
    item = _wav(application)
    original = item.markers[0]
    guid = original.guid
    item.remove_marker(original)
    new = item.add_marker(
        "item marker",
        Time(63504000000),
        comments="from py-premiere probe",
        duration=Time(127008000000),
    )
    new._write("mMarkerID", guid)
    core = item._own_clip_core()
    collection = application.project._document.resolve(core.find("MarkerOwner/Markers"))
    pair = collection.findall("Markers/Marker")[-1]
    pair.find("First").text = guid
    object_id = new._element.get("ObjectID")
    del application.project._document.by_object_id[object_id]
    new._element.set("ObjectID", "73")  # Premiere's slot for this marker
    pair.find("Second").set("ObjectRef", "73")
    application.project._document.by_object_id["73"] = new._element
    target = tmp_path / "readd.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert [m.name for m in _wav(fresh).markers] == ["item marker"]


def test_add_marker_on_bin_raises() -> None:
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")
    with pytest.raises(ValueError):
        application.project.root_item.children[0].add_marker("nope", Time(0))


def test_marking_an_item_that_has_no_collection_builds_one() -> None:
    # Whether an item arrives with a `MarkerOwner` depends on how it was
    # made - Premiere writes one for some imports and not others, and a
    # py-synthesized master has none at all - so the first add builds it,
    # between the property bag and `Source` where Premiere puts it
    # (samples/refs/gaps/clip_markers.prproj).
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    bare = [
        item
        for item in application.project.root_item.children
        if item._own_clip_core() is not None
        and item._own_clip_core().find("MarkerOwner") is None
    ]
    assert bare, "expected at least one item without a marker collection"
    item = bare[0]
    marker = item.add_marker("first", Time(254016000000), comments="hello")
    core = item._own_clip_core()
    tags = [child.tag for child in core]
    assert tags.index("MarkerOwner") == tags.index("Source") - 1
    assert [m.name for m in item.markers] == ["first"]
    assert marker.comments == "hello"
