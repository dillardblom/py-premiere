"""Adjustment-layer, merged-clip and multicam flags, and track locking.

All four come from hand-built GUI fixtures: none of these settings has a
scripting API in either ExtendScript or UXP, so they could only be made by
clicking. Each assertion matches the ExtendScript ground truth exported from
the same fixture.
"""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _item(application, name):
    return next(c for c in application.project.root_item.children if c.name == name)


def test_adjustment_layer() -> None:
    # Backed by Premiere's synthetic Black Video generator, so the flag on
    # the master clip - not the media - is what identifies it.
    application = py_premiere.parse(MINIMAL / "22_adjustment_layer.prproj")
    layer = _item(application, "Adjustment Layer")
    assert layer.is_adjustment_layer is True
    assert layer.is_merged_clip is False
    assert layer.is_multicam_clip is False
    # The synthetic Black Video media stores a fourcc token ('BLAK') where a
    # path would go, and neither ExtendScript (empty string) nor py (None)
    # reports it as a media path.
    assert layer.media_path is None


def test_merged_clip() -> None:
    application = py_premiere.parse(MINIMAL / "23_merged_clip.prproj")
    merged = _item(application, "bars_64x36_h264.mp4 - Merged")
    assert merged.is_merged_clip is True
    assert merged.is_multicam_clip is False
    assert merged.is_adjustment_layer is False


def test_multicam_clip() -> None:
    application = py_premiere.parse(MINIMAL / "24_multicam.prproj")
    multicam = _item(application, "bars_64x36_h264.mp4Multicam")
    assert multicam.is_multicam_clip is True
    # Both kinds are backed by a hidden sequence, so the merged flag has to
    # stay off here - that is the pair the derivation has to separate.
    assert multicam.is_merged_clip is False


def test_ordinary_items_are_none_of_those() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    for child in application.project.root_item.children:
        assert child.is_adjustment_layer is False
        assert child.is_merged_clip is False
        assert child.is_multicam_clip is False


def test_video_track_lock() -> None:
    application = py_premiere.parse(MINIMAL / "20_track_lock.prproj")
    sequence = next(s for s in application.project.sequences if s.name == "Seq B")
    assert [t.is_locked for t in sequence.video_tracks] == [True, False, False]
    assert [t.is_locked for t in sequence.audio_tracks] == [False, False, False]


def test_audio_track_lock() -> None:
    # Track mute lives in two different places for video and audio; lock
    # does NOT - both use ClipTrack/Track/IsLocked.
    application = py_premiere.parse(MINIMAL / "21_audio_track_lock.prproj")
    sequence = next(s for s in application.project.sequences if s.name == "Seq B")
    assert [t.is_locked for t in sequence.audio_tracks] == [True, False, False]
    assert [t.is_locked for t in sequence.video_tracks] == [False, False, False]


def test_unlocked_tracks_default_false() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    for sequence in application.project.sequences:
        for track in sequence.video_tracks + sequence.audio_tracks:
            assert track.is_locked is False
