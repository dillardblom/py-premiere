"""Track.is_locked write parity against the hand-locked fixtures."""

from __future__ import annotations

from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _seq_b(application):
    return next(s for s in application.project.sequences if s.name == "Seq B")


def test_locking_reproduces_the_fixture_bytes(tmp_path) -> None:
    # Locking V1 of 06_api through py must produce the same IsLocked element
    # Premiere wrote when the same track was locked by hand.
    application = py_premiere.parse(MINIMAL / "20_track_lock.prproj")
    track = _seq_b(application).video_tracks[0]
    assert track.is_locked is True
    original = (MINIMAL / "20_track_lock.prproj").read_bytes()

    track.is_locked = False
    track.is_locked = True
    target = tmp_path / "relocked.prproj"
    application.project.save(target)
    assert target.read_bytes() == original


def test_unlock_then_relock_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "21_audio_track_lock.prproj")
    track = _seq_b(application).audio_tracks[0]
    track.is_locked = False
    target = tmp_path / "unlocked.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    unlocked = next(s for s in fresh.project.sequences if s.name == "Seq B")
    assert unlocked.audio_tracks[0].is_locked is False
    unlocked.audio_tracks[0].is_locked = True
    relocked = tmp_path / "relocked.prproj"
    fresh.project.save(relocked)
    assert (
        relocked.read_bytes() == (MINIMAL / "21_audio_track_lock.prproj").read_bytes()
    )


def test_lock_is_independent_of_mute(tmp_path) -> None:
    # Both write into ClipTrack/Track for video; setting one must not
    # disturb the other.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = _seq_b(application).video_tracks[0]
    track.is_locked = True
    track.is_muted = True
    target = tmp_path / "both.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    reparsed = next(s for s in fresh.project.sequences if s.name == "Seq B")
    assert reparsed.video_tracks[0].is_locked is True
    assert reparsed.video_tracks[0].is_muted is True
    reparsed.video_tracks[0].is_muted = False
    assert reparsed.video_tracks[0].is_locked is True
