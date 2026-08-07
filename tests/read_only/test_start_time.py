"""ProjectItem.start_time against the `19_timecode` fixture."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"

#: Timecode 01:00:00:00 at 29.97 fps: 108000 frames of 8475667200 ticks.
HOUR_AT_2997 = 915372057600000


def test_timecoded_media_starts_at_its_timecode() -> None:
    application = py_premiere.parse(MINIMAL / "19_timecode.prproj")
    clip = application.project.root_item.children[0]
    assert clip.start_time.ticks == HOUR_AT_2997
    # The media in/out points are absolute, so they start there too.
    document = application.project._document
    logging_info = document.resolve(clip._master_element.find("LoggingInfo"))
    assert logging_info.findtext("MediaInPoint") == str(HOUR_AT_2997)
    # ...while the item's own in/out stay relative to the media start.
    assert clip.in_point.ticks == 0


def test_media_without_timecode_starts_at_zero() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    for child in application.project.root_item.children:
        assert child.start_time.ticks == 0


def test_bins_start_at_zero() -> None:
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")
    assert application.project.root_item.start_time.ticks == 0
    assert application.project.root_item.children[0].start_time.ticks == 0
