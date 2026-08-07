"""Keyframe interpolation against the `09_keyframes` fixture."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.enums import KeyframeInterpolation
from py_premiere.models import Time
from py_premiere.models.time import TICKS_PER_SECOND

FIXTURE = SAMPLES_DIR / "models" / "minimal" / "09_keyframes.prproj"

#: (seconds, value, mode) requested by the generating UXP call.
EXPECTED = [
    (0.5, 25.0, KeyframeInterpolation.LINEAR),
    (1.5, 75.0, KeyframeInterpolation.HOLD),
    (2.5, 50.0, KeyframeInterpolation.BEZIER),
    (3.5, 90.0, KeyframeInterpolation.BEZIER),
]


def _opacity_param() -> py_premiere.models.ComponentParam:
    application = py_premiere.parse(FIXTURE)
    clip = application.project.sequences[0].video_tracks[0].clips[0]
    component = next(c for c in clip.components if c.match_name == "AE.ADBE Opacity")
    return component.properties[0]


def test_keyframed_opacity() -> None:
    param = _opacity_param()
    assert param.display_name == "Opacity"
    assert param.is_time_varying
    keys = param.keys
    assert [k.seconds for k in keys] == [s for s, _, _ in EXPECTED]
    for key, (_, value, mode) in zip(keys, EXPECTED):
        assert param.get_value_at_key(key) == value
        assert param.get_interpolation_at_key(key) is mode


def test_interpolation_of_missing_key_is_none() -> None:
    param = _opacity_param()
    assert param.get_interpolation_at_key(Time(1)) is None


def _seconds(value: float) -> Time:
    return Time(round(value * TICKS_PER_SECOND))


def test_find_nearest_key() -> None:
    param = _opacity_param()
    # Nearest from either side, and from exactly on a key.
    assert param.find_nearest_key(_seconds(0.6)).seconds == 0.5
    assert param.find_nearest_key(_seconds(1.4)).seconds == 1.5
    assert param.find_nearest_key(_seconds(1.5)).seconds == 1.5
    # Past the last key, the last key is still the nearest.
    assert param.find_nearest_key(_seconds(10)).seconds == 3.5
    # A tie goes to the earlier key (1.0 sits between 0.5 and 1.5).
    assert param.find_nearest_key(_seconds(1.0)).seconds == 0.5


def test_find_nearest_key_honours_a_threshold() -> None:
    param = _opacity_param()
    assert param.find_nearest_key(_seconds(0.6), _seconds(0.2)).seconds == 0.5
    assert param.find_nearest_key(_seconds(10), _seconds(1)) is None


def test_find_next_and_previous_key() -> None:
    param = _opacity_param()
    assert param.find_next_key(_seconds(1.0)).seconds == 1.5
    assert param.find_previous_key(_seconds(1.0)).seconds == 0.5
    # Strictly after / strictly before: standing on a key steps off it.
    assert param.find_next_key(_seconds(1.5)).seconds == 2.5
    assert param.find_previous_key(_seconds(1.5)).seconds == 0.5
    assert param.find_next_key(_seconds(3.5)) is None
    assert param.find_previous_key(_seconds(0.5)) is None


def test_navigation_on_a_param_with_no_keys() -> None:
    application = py_premiere.parse(FIXTURE)
    clip = application.project.sequences[0].video_tracks[0].clips[0]
    param = next(
        p for component in clip.components for p in component.properties if not p.keys
    )
    assert param.find_nearest_key(Time(0)) is None
    assert param.find_next_key(Time(0)) is None
    assert param.find_previous_key(Time(0)) is None
