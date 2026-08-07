"""`TrackItem.set_time_remap` against the 25_time_remap fixture."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"
_SECOND = 254016000000


def _remapped_clip(
    application: py_premiere.models.Application,
) -> py_premiere.models.TrackItem:
    for sequence in application.project.sequences:
        for clip in sequence.clips:
            if clip.time_remapping is not None:
                return clip
    raise AssertionError("no remapped clip in the project")


def _fixture_keys(
    param: py_premiere.models.ComponentParam,
) -> list[tuple[Time, float]]:
    # Read back through the 24-decimal encoding: exact for any double.
    return [(time, param.get_value_at_key(time)) for time in param.keys]


def _leaves(element: ET.Element, base: str = "") -> dict[str, str]:
    out = {}
    for child in element:
        path = f"{base}/{child.tag}"
        if len(child):
            out.update(_leaves(child, path))
        else:
            out[path] = (child.text or "").strip()
    return out


def test_rewriting_same_curve_is_byte_identical(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "25_time_remap.prproj")
    clip = _remapped_clip(application)
    clip.set_time_remap(_fixture_keys(clip.time_remapping))
    target = tmp_path / "same.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "25_time_remap.prproj").read_bytes()


def test_recreating_matches_premieres_own_objects(tmp_path) -> None:
    # Clear Premiere's own curve, re-create it from the same keys, and the
    # synthesized objects must agree leaf-for-leaf with what Premiere wrote.
    application = py_premiere.parse(MINIMAL / "25_time_remap.prproj")
    clip = _remapped_clip(application)
    original = clip.time_remapping
    expected = _leaves(original._element)
    keys = _fixture_keys(original)

    clip.clear_time_remap()
    assert clip.time_remapping is None
    created = clip.set_time_remap(keys)
    assert _leaves(created._element) == expected
    core = clip._clip_element.find("Clip")
    tags = [child.tag for child in core]
    assert tags.index("TimeRemapping") == tags.index("Source") + 1

    target = tmp_path / "recreated.prproj"
    application.project.save(target)
    fresh_clip = _remapped_clip(parse_project_fresh(target))
    assert [k.ticks for k in fresh_clip.time_remapping.keys] == [
        k[0].ticks for k in keys
    ]


def test_create_on_a_virgin_clip_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    document = application.project._document
    before = len(list(document.root))
    clip = application.project.sequences[0].video_tracks[0].clips[0]
    assert clip.time_remapping is None
    clip.set_time_remap([(Time(0), 0.0), (Time(_SECOND), 2.0)])

    target = tmp_path / "virgin.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    param = fresh.project.sequences[0].video_tracks[0].clips[0].time_remapping
    assert param is not None
    # Premiere completes an unfinished curve with a terminal key at the
    # source end (the 12 h phantom still duration here), continuing at
    # unity speed - py appends the exact key Premiere would (measured off
    # the resave gate: 43199 s -> 43200 s).
    assert [k.ticks for k in param.keys] == [0, _SECOND, 43199 * _SECOND]
    assert param.get_value_at_key(Time(_SECOND)) == 2.0
    assert param.get_value_at_key(Time(43199 * _SECOND)) == 43200.0
    assert param._element.findtext("UpperBound") == "43200"

    clip.clear_time_remap()
    assert clip.time_remapping is None
    assert len(list(document.root)) == before


def test_set_time_remap_validation() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    clip = application.project.sequences[0].video_tracks[0].clips[0]
    with pytest.raises(ValueError, match="two keyframes"):
        clip.set_time_remap([(Time(0), 0.0)])
    with pytest.raises(ValueError, match="duplicate"):
        clip.set_time_remap([(Time(0), 0.0), (Time(0), 1.0)])
    with pytest.raises(ValueError, match="negative"):
        clip.set_time_remap([(Time(-1), 0.0), (Time(0), 1.0)])
    with pytest.raises(TypeError):
        clip.set_time_remap([(0, 0.0), (Time(0), 1.0)])
