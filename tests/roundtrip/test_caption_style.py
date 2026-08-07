"""Caption font-size styling against 29/64/80."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _track(application: py_premiere.models.Application):
    return next(
        s.caption_tracks[0] for s in application.project.sequences if s.caption_tracks
    )


def _payload(application: py_premiere.models.Application, index: int) -> bytes:
    caption = _track(application).captions[index]
    document = caption.track.sequence.project._document
    return document.payload(caption._text_data())


def test_font_size_reads() -> None:
    # Every as-imported caption carries the 48.0 run override; the caption
    # styled to 100 dropped it (the block base); 80 stores 75 inline.
    for fixture, expected in (
        ("29_captions", [48.0, 48.0]),
        ("64_caption_style", [100.0, 48.0]),
        ("80_subtitle_font_size_75", [75.0, 48.0]),
    ):
        application = py_premiere.parse(MINIMAL / f"{fixture}.prproj")
        sizes = [c.font_size for c in _track(application).captions]
        assert sizes == expected, fixture


def test_setting_75_matches_premieres_own_payload() -> None:
    # 80's styled block is byte-identical to the as-imported one except
    # the override float; py's write must reproduce it exactly.
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    expected = _payload(
        py_premiere.parse(MINIMAL / "80_subtitle_font_size_75.prproj"), 0
    )
    _track(application).captions[0].font_size = 75
    assert _payload(application, 0) == expected


def test_setting_100_drops_the_override_like_premiere() -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    expected = _payload(py_premiere.parse(MINIMAL / "64_caption_style.prproj"), 0)
    _track(application).captions[0].font_size = 100
    assert _payload(application, 0) == expected


def test_restoring_an_override_matches_premiere() -> None:
    # 64's first caption stores NO override (form B); setting 75 must
    # rebuild the override form byte-exactly (the B -> A transform).
    application = py_premiere.parse(MINIMAL / "64_caption_style.prproj")
    expected = _payload(
        py_premiere.parse(MINIMAL / "80_subtitle_font_size_75.prproj"), 0
    )
    _track(application).captions[0].font_size = 75
    assert _payload(application, 0) == expected


def test_font_size_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    track = _track(application)
    track.captions[0].font_size = 62.5
    assert track.captions[0].font_size == 62.5
    # The imported stream's own copy keeps its style.
    assert track.captions[1].font_size == 48.0
    target = tmp_path / "styled.prproj"
    application.project.save(target)
    fresh_track = _track(parse_project_fresh(target))
    assert fresh_track.captions[0].font_size == 62.5
    assert fresh_track.captions[1].font_size == 48.0
    assert fresh_track.captions[0].text == "Hello from py-premiere"


def test_font_size_on_py_created_captions(tmp_path) -> None:
    # End to end on py's own SRT import + caption track.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    item = application.project.import_files(
        [SAMPLES_DIR / "models" / "assets" / "two_lines.srt"]
    )[0]
    sequence = application.project.sequences[0]
    track = sequence.create_caption_track(item)
    track.captions[1].font_size = 75
    target = tmp_path / "styled_import.prproj"
    application.project.save(target)
    fresh_track = _track(parse_project_fresh(target))
    assert [c.font_size for c in fresh_track.captions] == [48.0, 75.0]


def test_font_size_validation() -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = _track(application).captions[0]
    with pytest.raises(TypeError):
        caption.font_size = "big"
    with pytest.raises(ValueError):
        caption.font_size = -1
