"""Caption and Essential Graphics text writes, end to end."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _track(application: py_premiere.models.Application):
    return next(
        s.caption_tracks[0] for s in application.project.sequences if s.caption_tracks
    )


def _source_text(application: py_premiere.models.Application):
    return next(
        p
        for sequence in application.project.sequences
        for clip in sequence.clips
        if "Text" in clip.components
        for p in clip.components["Text"].properties
        if p.display_name == "Source Text"
    )


def test_caption_text_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    track = _track(application)
    end_before = track.captions[0].end.ticks
    track.captions[0].text = "Rewritten by py-premiere"
    assert track.captions[0].text == "Rewritten by py-premiere"
    # The other caption is untouched.
    assert track.captions[1].text == "Second caption line"

    target = tmp_path / "retext.prproj"
    application.project.save(target)
    fresh = _track(parse_project_fresh(target))
    assert [c.text for c in fresh.captions] == [
        "Rewritten by py-premiere",
        "Second caption line",
    ]
    # Timing and styling survive the text change.
    assert fresh.captions[0].font_size == 48.0
    assert fresh.captions[0].end.ticks == end_before


def test_caption_text_keeps_a_restyled_size(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "80_subtitle_font_size_75.prproj")
    track = _track(application)
    track.captions[0].text = "Styled and retexted"
    target = tmp_path / "restyled_retext.prproj"
    application.project.save(target)
    fresh = _track(parse_project_fresh(target))
    assert fresh.captions[0].text == "Styled and retexted"
    assert fresh.captions[0].font_size == 75.0


def test_text_and_size_together(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = _track(application).captions[0]
    caption.text = "First change"
    caption.font_size = 62.5
    caption.text = "Second change"
    target = tmp_path / "both.prproj"
    application.project.save(target)
    fresh = _track(parse_project_fresh(target)).captions[0]
    assert fresh.text == "Second change"
    assert fresh.font_size == 62.5


def test_caption_text_validation() -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = _track(application).captions[0]
    with pytest.raises(ValueError):
        caption.text = ""
    with pytest.raises(TypeError):
        caption.text = 42


def test_eg_source_text_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "66_eg_text.prproj")
    param = _source_text(application)
    assert param.text == "py"
    param.text = "hello from py-premiere"
    target = tmp_path / "egtext.prproj"
    application.project.save(target)
    fresh = _source_text(parse_project_fresh(target))
    assert fresh.text == "hello from py-premiere"


def test_eg_text_write_refuses_mgt_controls() -> None:
    # A Motion Graphics template control stores UTF-16, not the
    # FormattedTextData FlatBuffer; rewriting one is not supported.
    application = py_premiere.parse(MINIMAL / "66_eg_text.prproj")
    param = _source_text(application)
    with pytest.raises(TypeError):
        param.text = None


def test_py_created_caption_text_round_trips(tmp_path) -> None:
    # End to end on py's own SRT import: retext a caption py synthesized.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    item = application.project.import_files(
        [SAMPLES_DIR / "models" / "assets" / "two_lines.srt"]
    )[0]
    track = application.project.sequences[0].create_caption_track(item)
    track.captions[1].text = "Edited after import"
    target = tmp_path / "imported_retext.prproj"
    application.project.save(target)
    fresh = _track(parse_project_fresh(target))
    assert [c.text for c in fresh.captions] == [
        "Hello from py-premiere",
        "Edited after import",
    ]
