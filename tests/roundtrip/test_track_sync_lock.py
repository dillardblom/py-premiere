"""Track.is_sync_locked against the QE-generated `32_sync_lock` fixture."""

from __future__ import annotations

from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"
FIXTURE = MINIMAL / "32_sync_lock.prproj"


def _seq_b(application: py_premiere.Application) -> py_premiere.Sequence:
    # QE's `getActiveSequence()` returns whatever sequence is FRONTED, which
    # for 06_api is Seq B - so that is where the flag landed.
    return next(s for s in application.project.sequences if s.name == "Seq B")


def test_sync_lock_read() -> None:
    # QE un-synced V1 and A1; everything else keeps the default, which
    # Premiere stores as nothing at all.
    application = py_premiere.parse(FIXTURE)
    sequence = _seq_b(application)
    assert sequence.video_tracks[0].is_sync_locked is False
    assert sequence.audio_tracks[0].is_sync_locked is False
    assert all(t.is_sync_locked for t in sequence.video_tracks[1:])
    assert all(t.is_sync_locked for t in sequence.audio_tracks[1:])
    other = py_premiere.parse(MINIMAL / "06_api.prproj")
    assert all(
        track.is_sync_locked
        for seq in other.project.sequences
        for track in seq.video_tracks + seq.audio_tracks
    )


def test_resyncing_then_unsyncing_reproduces_the_fixture(tmp_path) -> None:
    # Writing the flag must produce the exact element Premiere wrote.
    application = py_premiere.parse(FIXTURE)
    sequence = _seq_b(application)
    for track in (sequence.video_tracks[0], sequence.audio_tracks[0]):
        track.is_sync_locked = True
        track.is_sync_locked = False
    target = tmp_path / "resynced.prproj"
    application.project.save(target)
    assert target.read_bytes() == FIXTURE.read_bytes()


def test_unsyncing_a_default_track_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = _seq_b(application)
    sequence.video_tracks[1].is_sync_locked = False
    target = tmp_path / "unsynced.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    tracks = _seq_b(fresh).video_tracks
    assert tracks[1].is_sync_locked is False
    assert tracks[0].is_sync_locked is True
    tracks[1].is_sync_locked = True
    restored = tmp_path / "restored.prproj"
    fresh.project.save(restored)
    assert restored.read_bytes() == (MINIMAL / "06_api.prproj").read_bytes()


def test_sync_lock_is_independent_of_lock_and_mute(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = _seq_b(application).video_tracks[0]
    track.is_sync_locked = False
    track.is_locked = True
    track.is_muted = True
    target = tmp_path / "all_three.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    reparsed = _seq_b(fresh).video_tracks[0]
    assert reparsed.is_sync_locked is False
    assert reparsed.is_locked is True
    assert reparsed.is_muted is True
