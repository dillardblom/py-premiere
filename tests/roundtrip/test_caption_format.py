"""Caption format read/write against Premiere's own createCaptionTrack.

The expected XML per format comes from `sweep_caption_format.jsx`, which
called `Sequence.createCaptionTrack(item, 0, Sequence.CAPTION_FORMAT_*)`
for all seven constants and reported what each stored.
"""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.enums import CaptionFormat

MINIMAL = SAMPLES_DIR / "models" / "minimal"

#: (format, stored `Format`, stored `SubFormat`) as Premiere writes them.
SWEPT = [
    (CaptionFormat.SUBTITLE, None, None),
    (CaptionFormat.CEA_608, "1", None),
    (CaptionFormat.CEA_708, "2", None),
    (CaptionFormat.TELETEXT, "3", None),
    (CaptionFormat.EBU_SUBTITLE, "3", "1"),
    (CaptionFormat.OP42, "3", "2"),
    (CaptionFormat.OP47, "3", "3"),
]


def _track(application: py_premiere.models.Application):
    return next(
        s.caption_tracks[0] for s in application.project.sequences if s.caption_tracks
    )


@pytest.mark.parametrize(("value", "low", "high"), SWEPT)
def test_setting_each_format_stores_what_premiere_stores(value, low, high) -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    track = _track(application)
    track.format = value
    assert track._element.findtext("Format") == low
    assert track._element.findtext("SubFormat") == high
    assert track.format is value


@pytest.mark.parametrize(("value", "low", "high"), SWEPT)
def test_creating_with_each_format(value, low, high, tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    item = application.project.import_files(
        [SAMPLES_DIR / "models" / "assets" / "two_lines.srt"]
    )[0]
    sequence = application.project.sequences[0]
    track = sequence.create_caption_track(item, value)
    assert track.format is value
    target = tmp_path / f"fmt_{int(value)}.prproj"
    application.project.save(target)
    fresh = _track(parse_project_fresh(target))
    assert fresh.format is value
    assert fresh._element.findtext("Format") == low
    assert fresh._element.findtext("SubFormat") == high
    assert len(fresh.captions) == 2


def test_default_format_is_subtitle() -> None:
    # ExtendScript's captionFormat parameter defaults to SUBTITLE.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    item = application.project.import_files(
        [SAMPLES_DIR / "models" / "assets" / "two_lines.srt"]
    )[0]
    track = application.project.sequences[0].create_caption_track(item)
    assert track.format is CaptionFormat.SUBTITLE
    assert track._element.find("Format") is None


def test_format_switches_back_and_forth() -> None:
    # Going through a sub-formatted variant and back must leave no stray
    # SubFormat behind.
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    track = _track(application)
    track.format = CaptionFormat.OP47
    track.format = CaptionFormat.CEA_608
    assert track._element.findtext("Format") == "1"
    assert track._element.find("SubFormat") is None
    track.format = CaptionFormat.SUBTITLE
    assert track._element.find("Format") is None
    assert track._element.find("SubFormat") is None
    track.format = CaptionFormat.EBU_SUBTITLE
    assert track.format is CaptionFormat.EBU_SUBTITLE


def test_format_validation() -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    track = _track(application)
    with pytest.raises(ValueError):
        track.format = 7
    with pytest.raises(TypeError):
        track.format = "CEA-708"
    item = application.project.root_item.children["two_lines.srt"]
    sequence = application.project.sequences[0]
    with pytest.raises(ValueError):
        sequence.create_caption_track(item, 99)
