"""Ripple insert: parity with Premiere's insert edit."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _bmp(application: py_premiere.models.Application) -> py_premiere.models.ProjectItem:
    return next(
        c for c in application.project.root_item.children if c.name == "red_64x36.bmp"
    )


def test_ripple_insert_shifts_all_tracks_and_markers(tmp_path) -> None:
    # Verified against Premiere's own createInsertProjectItemAction: the
    # existing V1 clip, the A1 wav AND the sequence markers all shift by
    # the inserted duration (pr-compare: 0 objects only-in-either).
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    old_marker_starts = sorted(m.start.ticks for m in sequence.markers)
    placed = sequence.video_tracks[0].insert_clip(_bmp(application), Time(0))
    delta = placed.duration.ticks

    target = tmp_path / "ripple.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_seq = fresh.project.sequences[0]
    v1 = sorted(c.start.ticks for c in fresh_seq.video_tracks[0].clips)
    assert v1 == [0, delta]
    wav = fresh_seq.audio_tracks[0].clips[0]
    assert wav.start.ticks == 1262874412800 + delta
    assert sorted(m.start.ticks for m in fresh_seq.markers) == [
        t + delta for t in old_marker_starts
    ]


def test_ripple_insert_after_everything_shifts_nothing(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    wav_start = sequence.audio_tracks[0].clips[0].start.ticks
    late = Time(10 * 254016000000)
    placed = sequence.video_tracks[1].insert_clip(_bmp(application), late)
    assert placed.start.ticks == late.ticks
    assert sequence.audio_tracks[0].clips[0].start.ticks == wav_start


def test_ripple_insert_splitting_a_clip_raises() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    with pytest.raises(NotImplementedError):
        sequence.video_tracks[0].insert_clip(_bmp(application), Time(sequence.timebase))
