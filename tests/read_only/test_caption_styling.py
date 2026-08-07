"""Style slots named by 82_caption_style_sweep's sentinel values."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.models import Color

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _captions(fixture: str):
    application = py_premiere.parse(MINIMAL / f"{fixture}.prproj")
    return next(
        s.caption_tracks[0] for s in application.project.sequences if s.caption_tracks
    ).captions


def test_styled_caption_reads_its_sentinels() -> None:
    # The fixture's FIRST caption was styled through Essential Graphics,
    # each property to a distinctive value so the slots identify
    # themselves.
    styled = _captions("82_caption_style_sweep")[0]
    assert styled.font_size == 75.0
    assert styled.fill_color == Color(11, 22, 33)
    assert styled.stroke_color == Color(44, 55, 66)
    assert styled.stroke_width == 7.0
    assert styled.tracking == 17.0
    assert styled.leading == 23.0
    assert styled.shadow_color == Color(77, 88, 99)
    assert styled.shadow_opacity == 41.0
    # The text and family survived the styling.
    assert styled.text == "Hello from py-premiere"
    assert styled.font_family == "LucidaConsole"


def test_shadow_and_background_groups() -> None:
    # The Appearance panel's Shadow sliders read 41/45/46/47/48 and its
    # Background ones 42/43/44, which is exactly how the slots fall.
    styled = _captions("82_caption_style_sweep")[0]
    assert styled.shadow_opacity == 41.0
    assert styled.shadow_angle == 45.0
    assert styled.shadow_distance == 46.0
    assert styled.shadow_size == 47.0
    assert styled.shadow_blur == 48.0
    assert styled.background_color == Color(110, 120, 130)
    assert styled.background_opacity == 42.0
    assert styled.background_size == 43.0
    assert styled.background_corner_radius == 44.0


def test_untouched_caption_is_the_control() -> None:
    # The fixture's SECOND caption was left alone, which is what proves
    # the fill/stroke/tracking slots are per-RUN rather than per-block:
    # none of the first caption's sentinels reached it.
    control = _captions("82_caption_style_sweep")[1]
    assert control.font_size == 48.0
    assert control.fill_color is None
    assert control.stroke_color == Color(0, 0, 0)
    assert control.stroke_width == 0.0
    assert control.tracking is None


def test_unstyled_captions_carry_premieres_defaults() -> None:
    # An as-imported caption stores a black stroke of width ZERO (so no
    # visible edge) and no fill or tracking at all.
    for caption in _captions("29_captions"):
        assert caption.fill_color is None
        assert caption.stroke_color == Color(0, 0, 0)
        assert caption.stroke_width == 0.0
        assert caption.tracking is None
        assert caption.leading is None
        assert caption.shadow_color == Color(0, 0, 0)


def test_font_size_default_is_not_read_from_the_shadow_slot() -> None:
    # 64_caption_style's caption carries NO size override, so it renders at
    # the default 100. The block slot that reads 100 there is shadow
    # opacity (82 sets it to 41), so the default must be a constant - this
    # pins that the fallback no longer reads the wrong field.
    dropped = _captions("64_caption_style")[0]
    assert dropped.font_size == 100.0
    styled = _captions("82_caption_style_sweep")[0]
    assert styled.shadow_opacity == 41.0
    assert styled.font_size == 75.0
