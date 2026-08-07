"""Name lookup, iteration and walk over the model collections."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_sequences_by_name() -> None:
    project = py_premiere.parse(MINIMAL / "06_api.prproj").project
    sequence = project.sequences[0]
    assert project.sequences[sequence.name] is sequence
    assert sequence.name in project.sequences
    with pytest.raises(KeyError):
        project.sequences["No Such Sequence"]


def test_item_iteration_and_lookup() -> None:
    root = py_premiere.parse(MINIMAL / "02_bins.prproj").project.root_item
    assert list(root) == list(root.children)
    assert len(root) == len(root.children)
    first = root.children[0]
    assert root[first.name] is first
    assert root[0] is first
    assert first.name in root
    assert first in root


def test_walk_visits_nested_bins() -> None:
    root = py_premiere.parse(MINIMAL / "02_bins.prproj").project.root_item
    walked = list(root.walk())
    # walk goes deeper than the direct children.
    assert len(walked) > len(root.children)
    for child in root.children:
        assert child in walked


def test_track_iteration_and_flattened_clips() -> None:
    sequence = py_premiere.parse(MINIMAL / "06_api.prproj").project.sequences[0]
    track = sequence.video_tracks[0]
    assert list(track) == list(track.clips)
    assert len(track) == len(track.clips)
    assert sequence.video_tracks[track.name] is track
    flattened = sequence.clips
    assert len(flattened) == sum(
        len(t.clips) for t in list(sequence.video_tracks) + list(sequence.audio_tracks)
    )
    if flattened:
        clip = flattened[0]
        assert flattened[clip.name] is clip
        assert clip in track or any(clip in t for t in sequence.audio_tracks)


def test_component_lookup_by_name() -> None:
    # 05_features materializes Motion/Opacity on a placed clip.
    sequence = py_premiere.parse(MINIMAL / "05_features.prproj").project.sequences[0]
    clips = sequence.clips
    clip = next(c for c in clips if c.components)
    component = clip.components[0]
    assert clip.components[component.display_name] is component
    param = component.properties[0]
    assert component[param.display_name] is param
    assert list(component) == list(component.properties)
    assert len(component) == len(component.properties)
    assert param.display_name in component


def test_media_path_is_a_path() -> None:
    root = py_premiere.parse(MINIMAL / "03_one_clip.prproj").project.root_item
    clip = root.children[0]
    assert isinstance(clip.media_path, Path)
    assert clip.media_path.name == "red_64x36.bmp"


def test_item_points_none_without_media() -> None:
    root = py_premiere.parse(MINIMAL / "02_bins.prproj").project.root_item
    assert root.in_point is None
    assert root.out_point is None
    assert root.children[0].in_point is None
