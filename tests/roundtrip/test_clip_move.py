"""Moving a clip between tracks: byte-fidelity round-trip."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_move_clip_between_tracks(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    v1, v2 = sequence.video_tracks[0], sequence.video_tracks[1]
    clip = v1.clips[0]
    name = clip.name

    v1.move_clip(clip, v2, start=Time(sequence.timebase))
    assert v1.clips == []
    assert [c.name for c in v2.clips] == [name]
    assert clip.track is v2

    target = tmp_path / "moved.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_seq = fresh.project.sequences[0]
    assert fresh_seq.video_tracks[0].clips == []
    moved = fresh_seq.video_tracks[1].clips
    assert [c.name for c in moved] == [name]
    assert moved[0].start.ticks == sequence.timebase


def test_move_clip_across_media_type_raises() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    video_clip = sequence.video_tracks[0].clips[0]
    with pytest.raises(ValueError):
        sequence.video_tracks[0].move_clip(video_clip, sequence.audio_tracks[0])


def test_move_then_move_back(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    v1, v3 = sequence.video_tracks[0], sequence.video_tracks[2]
    clip = v1.clips[0]
    v1.move_clip(clip, v3)
    v3.move_clip(clip, v1)
    assert [c.name for c in v1.clips] == ["red_64x36.bmp"]
    assert v3.clips == []
    target = tmp_path / "back.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert [c.name for c in fresh.project.sequences[0].video_tracks[0].clips] == [
        "red_64x36.bmp"
    ]
