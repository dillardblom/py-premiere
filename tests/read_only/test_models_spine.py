"""Model-spine assertions over every local sample (no mutation)."""

from __future__ import annotations

from pathlib import Path

from helpers import each_sample

import py_premiere
from py_premiere.enums import ProjectItemType
from py_premiere.models import ProjectItem


def _walk(item: ProjectItem) -> list[ProjectItem]:
    found = [item]
    for child in item.children:
        found.extend(_walk(child))
    return found


def _is_real_project(path: Path) -> bool:
    # Premiere-written fixtures; the synthetic fixture has no item tree.
    return "templates" in path.parts or "resaves" in path.parts


@each_sample
def test_model_spine(path: Path) -> None:
    application = py_premiere.parse(path)
    project = application.project
    assert project.name == path.name

    if project.root_item is not None:
        assert project.root_item.type is ProjectItemType.ROOT
        items = _walk(project.root_item)
        clips = [i for i in items if i.type is ProjectItemType.CLIP]
        for clip in clips:
            assert clip.name
    if _is_real_project(path):
        assert project.root_item is not None
        assert project.sequences
        assert any(
            track.clips
            for sequence in project.sequences
            for track in sequence.video_tracks + sequence.audio_tracks
        )
        for sequence in project.sequences:
            assert sequence.sequence_id
            assert sequence.timebase
            assert sequence.frame_size is not None
            for track in sequence.video_tracks + sequence.audio_tracks:
                for clip in track.clips:
                    assert clip.end.ticks > clip.start.ticks
                    assert clip.in_point.ticks >= 0
                    assert clip.duration.ticks > 0
