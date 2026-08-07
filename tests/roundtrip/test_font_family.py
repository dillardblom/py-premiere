"""Font-family read/write on both styled-text surfaces."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models.caption import (
    decode_caption_text,
    read_font_family,
    read_font_size,
    write_font_family,
)

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


def test_font_family_reads_across_the_family() -> None:
    # Every fixture in the corpus is set in the same family.
    for fixture in ("29_captions", "64_caption_style", "80_subtitle_font_size_75"):
        application = py_premiere.parse(MINIMAL / f"{fixture}.prproj")
        families = [c.font_family for c in _track(application).captions]
        assert families == ["LucidaConsole", "LucidaConsole"], fixture
    application = py_premiere.parse(MINIMAL / "66_eg_text.prproj")
    assert _source_text(application).font_family == "LucidaConsole"


def test_font_family_write_keeps_text_and_size() -> None:
    # The family sits in a DIFFERENT string from the text, so splicing it
    # must leave both the text and the run's size override intact.
    application = py_premiere.parse(MINIMAL / "80_subtitle_font_size_75.prproj")
    caption = _track(application).captions[0]
    caption.font_family = "Arial"
    assert caption.font_family == "Arial"
    assert caption.text == "Hello from py-premiere"
    assert caption.font_size == 75.0


@pytest.mark.parametrize("name", ["A", "Arial", "Helvetica Neue", "x" * 120])
def test_font_family_write_round_trips_any_length(name: str) -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    document = application.project._document
    caption = _track(application).captions[0]
    caption.font_family = name
    payload = document.payload(caption._text_data())
    assert read_font_family(payload) == name
    assert decode_caption_text(payload) == "Hello from py-premiere"
    assert read_font_size(payload) == 48.0
    assert int.from_bytes(payload[:8], "little") == len(payload) - 12


def test_font_family_and_text_together(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = _track(application).captions[0]
    caption.font_family = "Verdana"
    caption.text = "Both changed"
    caption.font_size = 30
    target = tmp_path / "styled.prproj"
    application.project.save(target)

    fresh = _track(parse_project_fresh(target)).captions[0]
    assert (fresh.font_family, fresh.text, fresh.font_size) == (
        "Verdana",
        "Both changed",
        30.0,
    )


def test_eg_font_family_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "66_eg_text.prproj")
    param = _source_text(application)
    param.font_family = "Georgia"
    assert param.text == "py"
    target = tmp_path / "egfont.prproj"
    application.project.save(target)
    fresh = _source_text(parse_project_fresh(target))
    assert fresh.font_family == "Georgia"
    assert fresh.text == "py"


def test_authored_graphic_font_family(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = application.project.sequences[0].video_tracks[0]
    created = track.add_graphic("styled")
    param = created.components["Text"]["Source Text"]
    assert param.font_family == "LucidaConsole"
    param.font_family = "Impact"
    target = tmp_path / "authored_font.prproj"
    application.project.save(target)
    fresh = _source_text(parse_project_fresh(target))
    assert fresh.font_family == "Impact"
    assert fresh.text == "styled"


def test_font_family_validation() -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = _track(application).captions[0]
    with pytest.raises(ValueError):
        caption.font_family = ""
    with pytest.raises(TypeError):
        caption.font_family = 12
    application = py_premiere.parse(MINIMAL / "61_tint.prproj")
    # A parameter with no styled-text payload reads None and refuses writes.
    param = next(
        p
        for sequence in application.project.sequences
        for clip in sequence.clips
        if "Tint" in clip.components
        for p in clip.components["Tint"].properties
    )
    assert param.font_family is None
    with pytest.raises(ValueError):
        param.font_family = "Arial"


def test_write_font_family_refuses_empty() -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    document = application.project._document
    payload = document.payload(_track(application).captions[0]._text_data())
    with pytest.raises(ValueError, match="empty"):
        write_font_family(payload, "")
