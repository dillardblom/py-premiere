"""Keyframe writes: byte-fidelity + tangent-formula parity with Premiere."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.enums import KeyframeInterpolation as KI
from py_premiere.models import Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"
_SECOND = 254016000000


def _opacity(
    application: py_premiere.models.Application,
) -> py_premiere.models.ComponentParam:
    clip = application.project.sequences[0].video_tracks[0].clips[0]
    component = next(c for c in clip.components if c.match_name == "AE.ADBE Opacity")
    return component.properties[0]


def _keys() -> list[tuple[Time, float, KI]]:
    return [
        (Time(round(0.5 * _SECOND)), 25, KI.LINEAR),
        (Time(round(1.5 * _SECOND)), 75, KI.HOLD),
        (Time(round(2.5 * _SECOND)), 50, KI.BEZIER),
        (Time(round(3.5 * _SECOND)), 90, KI.BEZIER),
    ]


def test_rewriting_same_keyframes_is_byte_identical(tmp_path) -> None:
    # The auto-computed tangents reproduce Premiere's own output exactly.
    application = py_premiere.parse(MINIMAL / "09_keyframes.prproj")
    _opacity(application).set_keyframes(_keys())
    target = tmp_path / "same.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "09_keyframes.prproj").read_bytes()


def test_set_new_keyframes_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "09_keyframes.prproj")
    _opacity(application).set_keyframes(
        [(Time(_SECOND), 10, KI.LINEAR), (Time(2 * _SECOND), 90, KI.LINEAR)]
    )
    target = tmp_path / "new.prproj"
    application.project.save(target)

    param = _opacity(parse_project_fresh(target))
    times = [k.seconds for k in param.keys]
    assert times == [1.0, 2.0]
    assert param.get_value_at_key(param.keys[0]) == 10.0
    assert param.get_interpolation_at_key(param.keys[1]) is KI.LINEAR


def test_keyframes_accept_unordered_input(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "09_keyframes.prproj")
    _opacity(application).set_keyframes(
        [(Time(3 * _SECOND), 40, KI.LINEAR), (Time(_SECOND), 80, KI.LINEAR)]
    )
    target = tmp_path / "unordered.prproj"
    application.project.save(target)
    param = _opacity(parse_project_fresh(target))
    assert [k.seconds for k in param.keys] == [1.0, 3.0]


def test_materialize_keyframes_on_static_param(tmp_path) -> None:
    # A static scalar becomes keyframed (Keyframes element + IsTimeVarying).
    application = py_premiere.parse(MINIMAL / "10_audio_volume.prproj")
    clip = application.project.sequences[0].audio_tracks[0].clips[0]
    level = next(p for p in clip.components[0].properties if p.display_name == "Level")
    assert not level.is_time_varying
    level.set_keyframes(
        [
            (Time(round(0.25 * _SECOND)), 0.25, KI.LINEAR),
            (Time(round(0.75 * _SECOND)), 0.75, KI.LINEAR),
        ]
    )
    assert level.is_time_varying

    target = tmp_path / "materialized.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_clip = fresh.project.sequences[0].audio_tracks[0].clips[0]
    fresh_level = next(
        p for p in fresh_clip.components[0].properties if p.display_name == "Level"
    )
    assert fresh_level.is_time_varying
    assert [round(k.seconds, 2) for k in fresh_level.keys] == [0.25, 0.75]


def test_materialize_keyframes_writes_the_time_varying_flag(tmp_path) -> None:
    # Premiere carries <IsTimeVarying> on every keyframed video param and
    # elides it while static, so keyframing one must create the element -
    # right after <Name>, where Premiere's own output puts it.
    application = py_premiere.parse(MINIMAL / "05_features.prproj")
    param = _scale(application)
    assert param._element.find("IsTimeVarying") is None
    param.set_keyframes([(Time(0), 50, KI.LINEAR), (Time(_SECOND), 75, KI.LINEAR)])

    target = tmp_path / "flagged.prproj"
    application.project.save(target)
    fresh = _scale(parse_project_fresh(target))
    assert fresh._element.findtext("IsTimeVarying") == "true"
    assert [child.tag for child in fresh._element][:2] == ["Name", "IsTimeVarying"]


#: Premiere's own keyframe string for 63_audio_keyframes' Level param:
#: fractional values at 12 significant figures and slopes derived from the
#: FLOAT32-rounded values (0.60000000894069672 = float32(0.8) - float32(0.2)).
_AUDIO_KEYFRAMES = (
    "254016000000,0.20000000298,0,0,0,0.16666666666666666,"
    "0.60000000894069672,0.16666666666666666;"
    "508032000000,0.800000011921,0,0,0.60000000894069672,"
    "0.16666666666666666,0,0.16666666666666666;"
)


def _audio_level(
    application: py_premiere.models.Application,
) -> py_premiere.models.ComponentParam:
    clip = application.project.sequences[0].audio_tracks[0].clips[0]
    return next(p for p in clip.components[0].properties if p.display_name == "Level")


def test_audio_keyframe_rewrite_is_byte_identical(tmp_path) -> None:
    # Rewriting 63's own keys must reproduce Premiere's exact keyframe
    # string - fractional slopes and 12-sig-fig values included.
    application = py_premiere.parse(MINIMAL / "63_audio_keyframes.prproj")
    _audio_level(application).set_keyframes(
        [(Time(_SECOND), 0.2, KI.LINEAR), (Time(2 * _SECOND), 0.8, KI.LINEAR)]
    )
    target = tmp_path / "same_audio.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "63_audio_keyframes.prproj").read_bytes()


def test_audio_materialize_matches_premieres_own_shape(tmp_path) -> None:
    # Keyframing the still-static 10_audio_volume Level must produce what
    # Premiere produced from the same starting point (63_audio_keyframes):
    # the same keyframe string, the `IsTimeVarying` flag DELETED (audio
    # drops it), and `Keyframes` placed after `CurrentValue`. Premiere also
    # stamps a session Timestamp, which py deliberately omits.
    application = py_premiere.parse(MINIMAL / "10_audio_volume.prproj")
    level = _audio_level(application)
    assert level._element.find("IsTimeVarying") is not None
    level.set_keyframes(
        [(Time(_SECOND), 0.2, KI.LINEAR), (Time(2 * _SECOND), 0.8, KI.LINEAR)]
    )
    assert level._element.findtext("Keyframes") == _AUDIO_KEYFRAMES
    assert level._element.find("IsTimeVarying") is None
    tags = [child.tag for child in level._element]
    assert tags.index("Keyframes") == tags.index("CurrentValue") + 1

    target = tmp_path / "audio_materialized.prproj"
    application.project.save(target)
    fresh = _audio_level(parse_project_fresh(target))
    assert fresh.is_time_varying
    assert fresh._element.findtext("Keyframes") == _AUDIO_KEYFRAMES


def test_set_keyframes_requires_keys() -> None:
    application = py_premiere.parse(MINIMAL / "09_keyframes.prproj")
    with pytest.raises(ValueError):
        _opacity(application).set_keyframes([])


def _scale(
    application: py_premiere.models.Application,
) -> py_premiere.models.ComponentParam:
    clip = application.project.sequences[0].video_tracks[0].clips[0]
    component = next(c for c in clip.components if c.match_name == "AE.ADBE Motion")
    return next(p for p in component.properties if p.display_name == "Scale")


def test_set_keyframes_rejects_duplicate_times_without_mutating() -> None:
    application = py_premiere.parse(MINIMAL / "05_features.prproj")
    param = _scale(application)
    before = ET.tostring(param._element, encoding="unicode")
    with pytest.raises(ValueError, match="duplicate keyframe time"):
        param.set_keyframes([(Time(0), 1.0, KI.LINEAR), (Time(0), 2.0, KI.LINEAR)])
    assert ET.tostring(param._element, encoding="unicode") == before


def test_set_keyframes_rejects_out_of_range_value_without_mutating() -> None:
    application = py_premiere.parse(MINIMAL / "05_features.prproj")
    param = _scale(application)
    before = ET.tostring(param._element, encoding="unicode")
    with pytest.raises(ValueError):
        param.set_keyframes([(Time(0), 1e300, KI.LINEAR)])
    # A refused call must leave no half-written param behind.
    assert ET.tostring(param._element, encoding="unicode") == before
    assert param.is_time_varying is False


def test_set_keyframes_rejects_a_non_time() -> None:
    application = py_premiere.parse(MINIMAL / "05_features.prproj")
    with pytest.raises(TypeError):
        _scale(application).set_keyframes([(0, 1.0, KI.LINEAR)])


def test_keyframe_readers_reject_a_non_time() -> None:
    application = py_premiere.parse(MINIMAL / "09_keyframes.prproj")
    param = _opacity(application)
    with pytest.raises(TypeError):
        param.get_value_at_key(0)
    with pytest.raises(TypeError):
        param.get_interpolation_at_key(0)
