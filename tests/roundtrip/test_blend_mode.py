"""Blend modes against 81_blend_modes."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.enums import BlendMode
from py_premiere.models.track_item import _API_BLEND_VALUES

MINIMAL = SAMPLES_DIR / "models" / "minimal"

#: The fixture's 27 clips carry the popup rows in order.
POPUP_ORDER = [
    BlendMode.NORMAL,
    BlendMode.DISSOLVE,
    BlendMode.DARKEN,
    BlendMode.MULTIPLY,
    BlendMode.COLOR_BURN,
    BlendMode.LINEAR_BURN,
    BlendMode.DARKER_COLOR,
    BlendMode.LIGHTEN,
    BlendMode.SCREEN,
    BlendMode.COLOR_DODGE,
    BlendMode.LINEAR_DODGE,
    BlendMode.LIGHTER_COLOR,
    BlendMode.OVERLAY,
    BlendMode.SOFT_LIGHT,
    BlendMode.HARD_LIGHT,
    BlendMode.VIVID_LIGHT,
    BlendMode.LINEAR_LIGHT,
    BlendMode.PIN_LIGHT,
    BlendMode.HARD_MIX,
    BlendMode.DIFFERENCE,
    BlendMode.EXCLUSION,
    BlendMode.SUBTRACT,
    BlendMode.DIVIDE,
    BlendMode.HUE,
    BlendMode.SATURATION,
    BlendMode.COLOR,
    BlendMode.LUMINOSITY,
]


def _clips(application: py_premiere.models.Application):
    for sequence in application.project.sequences:
        for track in sequence.video_tracks:
            clips = sorted(track.clips, key=lambda c: c.start.ticks)
            if len(clips) >= 27:
                return clips
    raise AssertionError("no 27-clip track in the project")


def _normalized(element: ET.Element) -> str:
    text = ET.tostring(element, encoding="unicode").rstrip("\n\t")
    return re.sub(r'(Object(?:ID|Ref))="\d+"', r'\1="N"', text)


def _opacity_closure(application, clip):
    document = application.project._document
    chain = document.resolve(
        clip._element.find("ClipTrackItem/ComponentOwner/Components")
    )
    component = next(
        c
        for c in clip.components
        if c._element.findtext("Component/DisplayName") == "Opacity"
    )
    return chain, component._element, [p._element for p in component.properties]


def test_all_27_modes_read_in_popup_order() -> None:
    application = py_premiere.parse(MINIMAL / "81_blend_modes.prproj")
    assert [c.blend_mode for c in _clips(application)] == POPUP_ORDER


def test_materialization_matches_premieres_own() -> None:
    # Clip 1 was never touched; setting Multiply on it must produce the
    # chain state, component and all three params exactly as Premiere
    # stored them on clip 4 (ObjectIDs aside).
    application = py_premiere.parse(MINIMAL / "81_blend_modes.prproj")
    clips = _clips(application)
    chain, component, params = _opacity_closure(application, clips[3])
    expected = [_normalized(e) for e in (chain, component, *params)]

    clips[0].blend_mode = BlendMode.MULTIPLY
    chain, component, params = _opacity_closure(application, clips[0])
    actual = [_normalized(e) for e in (chain, component, *params)]
    assert actual == expected


def test_blend_mode_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    clip = next(
        c
        for s in application.project.sequences
        for t in s.video_tracks
        for c in t.clips
    )
    assert clip.blend_mode is BlendMode.NORMAL
    clip.blend_mode = BlendMode.SCREEN
    assert clip.blend_mode is BlendMode.SCREEN
    # A second write updates the materialized params in place - both twins.
    clip.blend_mode = BlendMode.DARKEN
    params = clip._blend_params()
    assert params["3"]._element.findtext("StartKeyframe") == (
        "-91445760000000000,3,0,0,0,0,0,0"
    )
    assert params["2"]._element.findtext("StartKeyframe") == (
        "-91445760000000000,3,0,0,0,0,0,0"
    )
    target = tmp_path / "blend.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_clip = next(
        c for s in fresh.project.sequences for t in s.video_tracks for c in t.clips
    )
    assert fresh_clip.blend_mode is BlendMode.DARKEN


def test_blend_mode_validation() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    clip = next(
        c
        for s in application.project.sequences
        for t in s.video_tracks
        for c in t.clips
    )
    with pytest.raises(TypeError):
        clip.blend_mode = "Multiply"
    # Setting NORMAL on an untouched clip stays a no-op.
    clip.blend_mode = BlendMode.NORMAL
    assert clip._element.find("ClipTrackItem/ComponentOwner") is not None
    assert clip.blend_mode is BlendMode.NORMAL


def test_resetting_every_stored_mode_is_byte_identical() -> None:
    # The popup twin (ParameterID 2) counts in its own alphabetical order,
    # which is NOT the enum's: Lighten 11, Lighter Color 12, Linear Burn 13,
    # Linear Dodge 14, Linear Light 15. Re-setting each clip's own mode has
    # to reproduce Premiere's bytes, which a swapped pair would not.
    source = MINIMAL / "81_blend_modes.prproj"
    application = py_premiere.parse(source)
    touched = 0
    for sequence in application.project.sequences:
        for track in sequence.video_tracks:
            for clip in track.clips:
                clip.blend_mode = clip.blend_mode
                touched += 1
    assert touched >= 27
    assert application.project._document.to_bytes() == source.read_bytes()


def test_popup_values_are_a_complete_bijection() -> None:

    assert sorted(_API_BLEND_VALUES.values()) == list(range(27))
    assert len(_API_BLEND_VALUES) == len(BlendMode)
