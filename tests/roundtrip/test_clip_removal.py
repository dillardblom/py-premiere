"""Timeline clip removal: byte-fidelity round-trip."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.enums import ProjectItemType

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_remove_clip_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]  # Seq A
    track = sequence.video_tracks[0]
    assert [c.name for c in track.clips] == ["red_64x36.bmp"]

    track.remove_clip(track.clips[0])
    assert track.clips == []

    target = tmp_path / "removed.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert fresh.project.sequences[0].video_tracks[0].clips == []
    # The source master clip stays in the project panel.
    names = {c.name for c in fresh.project.root_item.children}
    assert "red_64x36.bmp" in names


def test_remove_audio_clip_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = application.project.sequences[0].audio_tracks[0]
    assert track.clips
    track.remove_clip(track.clips[0])
    target = tmp_path / "removed_audio.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert fresh.project.sequences[0].audio_tracks[0].clips == []


def test_remove_foreign_clip_raises() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    other_clip = sequence.audio_tracks[0].clips[0]
    with pytest.raises(ValueError):
        sequence.video_tracks[0].remove_clip(other_clip)


def test_project_still_valid_after_removal(tmp_path) -> None:
    # Removing a timeline clip must not disturb the project item tree.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    before = len(
        [
            c
            for c in application.project.root_item.children
            if c.type is ProjectItemType.CLIP
        ]
    )
    application.project.sequences[0].video_tracks[0].remove_clip(
        application.project.sequences[0].video_tracks[0].clips[0]
    )
    target = tmp_path / "x.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    after = len(
        [c for c in fresh.project.root_item.children if c.type is ProjectItemType.CLIP]
    )
    assert after == before


def test_removing_an_audio_clip_takes_its_secondary_content(tmp_path) -> None:
    source = MINIMAL / "06_api.prproj"
    application = py_premiere.parse(source)
    track = application.project.sequences[0].audio_tracks[0]
    placed = track.add_clip(
        next(
            c
            for c in application.project.root_item.children
            if c.name == "renamed tone"
        )
    )
    track.remove_clip(placed)
    # Add + remove must come back to the original bytes: the placement's own
    # SecondaryContent objects go with it.
    target = tmp_path / "roundtrip.prproj"
    application.project.save(target)
    assert target.read_bytes() == source.read_bytes()
