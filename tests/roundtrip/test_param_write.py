"""Scalar parameter value writes: byte-fidelity + format parity."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Color

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _level(
    application: py_premiere.models.Application,
) -> py_premiere.models.ComponentParam:
    clip = application.project.sequences[0].audio_tracks[0].clips[0]
    return next(p for p in clip.components[0].properties if p.display_name == "Level")


def test_set_value_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "10_audio_volume.prproj")
    _level(application).value = 0.5
    target = tmp_path / "set.prproj"
    application.project.save(target)
    assert _level(parse_project_fresh(target)).value == 0.5


def test_set_value_uses_float32_like_premiere(tmp_path) -> None:
    # 0.35 is not float32-exact; Premiere (and py) store 0.34999999404.
    application = py_premiere.parse(MINIMAL / "10_audio_volume.prproj")
    _level(application).value = 0.35
    raw = _level(application)._element.findtext("StartKeyframe")
    assert raw is not None and raw.split(",")[1] == "0.34999999404"


def test_set_to_same_value_is_byte_identical(tmp_path) -> None:
    # The fixture's Level is 0.35; re-setting it reproduces Premiere's bytes.
    application = py_premiere.parse(MINIMAL / "10_audio_volume.prproj")
    _level(application).value = 0.35
    target = tmp_path / "same.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "10_audio_volume.prproj").read_bytes()


def test_set_value_integer_trailing_dot() -> None:
    application = py_premiere.parse(MINIMAL / "10_audio_volume.prproj")
    param = _level(application)
    param.value = 1
    assert param._element.findtext("StartKeyframe").split(",")[1] == "1."


def test_set_value_on_keyframed_raises() -> None:
    application = py_premiere.parse(MINIMAL / "09_keyframes.prproj")
    clip = application.project.sequences[0].video_tracks[0].clips[0]
    opacity = next(c for c in clip.components if c.match_name == "AE.ADBE Opacity")
    param = opacity.properties[0]
    assert param.is_time_varying
    with pytest.raises(ValueError):
        param.value = 50


def _param(
    application: py_premiere.models.Application, name: str
) -> py_premiere.models.ComponentParam:
    seq = application.project.sequences[0]
    for track in seq.video_tracks + seq.audio_tracks:
        for clip in track.clips:
            for component in clip.components:
                for param in component.properties:
                    if param.display_name == name:
                        return param
    raise AssertionError(f"param {name!r} not found")


def test_set_point_value_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "05_features.prproj")
    _param(application, "Position").value = [0.25, 0.75]
    target = tmp_path / "point.prproj"
    application.project.save(target)
    assert _param(parse_project_fresh(target), "Position").value == [0.25, 0.75]


def test_set_point_to_same_value_is_byte_identical() -> None:
    # Position is 0.5:0.5; re-setting it reproduces Premiere's exact bytes.
    application = py_premiere.parse(MINIMAL / "05_features.prproj")
    param = _param(application, "Position")
    original = param._element.findtext("StartKeyframe")
    param.value = [0.5, 0.5]
    assert param._element.findtext("StartKeyframe") == original


def test_set_bool_value_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "05_features.prproj")
    param = _param(application, " ")  # the checkbox param
    assert param.value is True
    param.value = False
    target = tmp_path / "bool.prproj"
    application.project.save(target)
    assert _param(parse_project_fresh(target), " ").value is False


def test_set_bool_rejects_non_bool() -> None:
    application = py_premiere.parse(MINIMAL / "05_features.prproj")
    with pytest.raises(TypeError):
        _param(application, " ").value = 1


def test_set_point_rejects_wrong_length() -> None:
    application = py_premiere.parse(MINIMAL / "05_features.prproj")
    with pytest.raises(TypeError):
        _param(application, "Position").value = [0.5, 0.5, 0.5]


def test_small_scalar_value_reads_back_as_a_number(tmp_path) -> None:
    # `%g` switches to exponent form below 1e-4, a shape Premiere never
    # writes and the decoder does not recognise as a number.
    application = py_premiere.parse(MINIMAL / "10_audio_volume.prproj")
    _level(application).value = 0.00002
    target = tmp_path / "tiny.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    value = _level(fresh).value
    assert isinstance(value, float)
    assert abs(value - 0.00002) < 1e-9
    text = target.read_bytes()
    assert b"e-05" not in text and b"e-005" not in text


def test_scalar_value_rejects_out_of_float32_range() -> None:
    application = py_premiere.parse(MINIMAL / "10_audio_volume.prproj")
    param = _level(application)
    before = param.value
    with pytest.raises(ValueError):
        param.value = 1e300
    assert param.value == before


def test_set_value_updates_the_current_value_mirror() -> None:
    # Audio scalars mirror the static value in `CurrentValue`; a stale
    # mirror would diverge from Premiere's own setValue output.
    application = py_premiere.parse(MINIMAL / "10_audio_volume.prproj")
    param = _level(application)
    param.value = 0.5
    assert param._element.findtext("CurrentValue") == "0.5"


def _tint(
    application: py_premiere.models.Application,
) -> py_premiere.models.Component:
    for sequence in application.project.sequences:
        for clip in sequence.clips:
            if "Tint" in clip.components:
                return clip.components["Tint"]
    raise AssertionError("no Tint component in the project")


def test_set_color_to_same_value_is_byte_identical(tmp_path) -> None:
    # 61_tint stores Premiere's own Tint defaults: ALPHA-0 black and white
    # packings, written as bare decimal integers (no trailing dot).
    application = py_premiere.parse(MINIMAL / "61_tint.prproj")
    tint = _tint(application)
    tint["Map Black To"].color = Color(0, 0, 0, 0)
    tint["Map White To"].color = Color(255, 255, 255, 0)
    target = tmp_path / "same_color.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "61_tint.prproj").read_bytes()


def test_set_color_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "61_tint.prproj")
    _tint(application)["Map Black To"].color = Color(255, 136, 0, 0)
    target = tmp_path / "color.prproj"
    application.project.save(target)
    assert _tint(parse_project_fresh(target))["Map Black To"].color == Color(
        255, 136, 0, 0
    )


def test_set_color_via_the_packed_value() -> None:
    # ES parity: `value` accepts the raw packed uint64 on a color param.
    application = py_premiere.parse(MINIMAL / "61_tint.prproj")
    param = _tint(application)["Map White To"]
    param.value = 280379743338240
    raw = param._element.findtext("StartKeyframe")
    assert raw is not None and raw.split(",")[1] == "280379743338240"


def test_color_setter_validation() -> None:
    application = py_premiere.parse(MINIMAL / "61_tint.prproj")
    tint = _tint(application)
    param = tint["Map Black To"]
    with pytest.raises(TypeError):
        param.color = (255, 0, 0)  # a plain tuple is not a Color
    with pytest.raises(ValueError):
        param.color = Color(256, 0, 0, 0)
    with pytest.raises(ValueError):
        param.value = -1
    with pytest.raises(ValueError):
        tint["Amount to Tint"].color = Color(0, 0, 0)


def test_gui_picked_color_matches_61b() -> None:
    # 61b_tint_color: Map Black To = FF8800 through the colour picker. The
    # stored packing carries ALPHA FF (Color's default) - unlike the Tint
    # DEFAULTS, which pack alpha 0 - and py's setter reproduces Premiere's
    # keyframe text exactly.
    application = py_premiere.parse(MINIMAL / "61_tint.prproj")
    reference = py_premiere.parse(MINIMAL / "61b_tint_color.prproj")
    param = _tint(application)["Map Black To"]
    param.color = Color(255, 136, 0)
    expected = _tint(reference)["Map Black To"]._element.findtext("StartKeyframe")
    assert expected is not None and expected.split(",")[1] == "18374966857418407936"
    assert param._element.findtext("StartKeyframe") == expected
