"""`ProjectItem.start_time` writes against Premiere's own setStartTime."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"

#: 02:00:00:00 at 29.97 ND: what 62_start_time's ES setStartTime wrote.
_TWO_HOURS = 1830744115200000


def test_set_to_same_value_is_byte_identical(tmp_path) -> None:
    # Premiere's own edit touched Media/AlternateStart alone; re-setting the
    # stored value must reproduce the fixture byte-for-byte.
    application = py_premiere.parse(MINIMAL / "62_start_time.prproj")
    item = application.project.root_item.children[0]
    item.start_time = Time(_TWO_HOURS)
    target = tmp_path / "same.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "62_start_time.prproj").read_bytes()


def test_replaying_premieres_edit_round_trips(tmp_path) -> None:
    # The same edit Premiere made for 62_start_time, replayed on the base.
    application = py_premiere.parse(MINIMAL / "19_timecode.prproj")
    item = application.project.root_item.children[0]
    assert item.start_time == Time(915372057600000)
    item.start_time = Time(_TWO_HOURS)
    assert item.start_time == Time(_TWO_HOURS)
    target = tmp_path / "moved.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert fresh.project.root_item.children[0].start_time == Time(_TWO_HOURS)


def test_refuses_media_without_a_stored_timecode() -> None:
    # No reference exists for synthesizing AlternateStart/UseAlternateStart
    # from scratch, so timecode-less media refuses rather than guessing.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    item = application.project.root_item.children[0]
    with pytest.raises(ValueError, match="start timecode"):
        item.start_time = Time(0)


def test_rejects_a_negative_time_and_a_non_time() -> None:
    application = py_premiere.parse(MINIMAL / "62_start_time.prproj")
    item = application.project.root_item.children[0]
    with pytest.raises(ValueError):
        item.start_time = Time(-1)
    with pytest.raises(TypeError):
        item.start_time = 0
