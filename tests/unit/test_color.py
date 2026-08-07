"""Color param unpacking (bit layout locked against known values)."""

from __future__ import annotations

from py_premiere.models import Color
from py_premiere.models.component import _unpack_color


def test_white() -> None:
    # 0xff00ff00ff00ff00 -> opaque white (verified via UXP).
    assert _unpack_color(0xFF00FF00FF00FF00) == Color(255, 255, 255, 255)


def test_known_colors() -> None:
    # From the Abstract Slideshow / VHS resave color params, each confirmed
    # against Premiere's own RGB (UXP getStartValue).
    assert _unpack_color(0xFF00DE0054001800) == Color(222, 84, 24, 255)
    assert _unpack_color(0xFF00FF00A0005B00) == Color(255, 160, 91, 255)
    assert _unpack_color(0xFF00A300F7008F00) == Color(163, 247, 143, 255)


def test_channels_independent() -> None:
    assert _unpack_color(0x0000FF0000000000) == Color(255, 0, 0, 0)
    assert _unpack_color(0x000000000000FF00) == Color(0, 0, 255, 0)
    assert _unpack_color(0xFF00000000000000) == Color(0, 0, 0, 255)


def test_color_defaults_alpha() -> None:
    assert Color(1, 2, 3) == Color(1, 2, 3, 255)
