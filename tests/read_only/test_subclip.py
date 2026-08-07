"""Subclip boundaries against the `28_subclip` fixture."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.models import ProjectItem

FIXTURE = SAMPLES_DIR / "models" / "minimal" / "28_subclip.prproj"
# createSubClip("h264 subclip", "63504000000", "190512000000", 0, 1, 1)
IN_TICKS = 63504000000
OUT_TICKS = 190512000000


def _item(name: str) -> ProjectItem:
    application = py_premiere.parse(FIXTURE)
    for item in application.project.root_item.children:
        if item.name == name:
            return item
    raise AssertionError(f"no item named {name!r}")


def test_subclip_boundaries() -> None:
    subclip = _item("h264 subclip")
    assert subclip.is_subclip is True
    assert subclip.subclip_in_point is not None
    assert subclip.subclip_in_point.ticks == IN_TICKS
    assert subclip.subclip_out_point is not None
    assert subclip.subclip_out_point.ticks == OUT_TICKS
    # Created with hardBoundaries 0.
    assert subclip.has_hard_boundaries is False


def test_subclip_in_out_still_span_the_whole_file() -> None:
    # The narrowing lives ONLY in the boundaries: the master clip's own in
    # and out points still describe the full media.
    subclip = _item("h264 subclip")
    source = _item("bars_64x36_h264.mp4")
    assert subclip.in_point.ticks == source.in_point.ticks
    assert subclip.out_point.ticks == source.out_point.ticks
    assert subclip.media_path == source.media_path


def test_ordinary_items_are_not_subclips() -> None:
    source = _item("bars_64x36_h264.mp4")
    assert source.is_subclip is False
    assert source.subclip_in_point is None
    assert source.subclip_out_point is None
    assert source.has_hard_boundaries is False
