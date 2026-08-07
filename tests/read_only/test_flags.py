"""Exposed flag/derived accessors: is_sequence, speed, reverse, mute.

Validated against Premiere-authored fixtures where the values are stored
(the minimal corpus for sequence-backed items, the resaves for speed /
reverse / mute, whose flags Premiere wrote out).
"""

from __future__ import annotations

from helpers import SAMPLES_DIR, require_sample

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"
RESAVES = SAMPLES_DIR / "resaves"


def test_is_sequence() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    by_name = {c.name: c.is_sequence for c in application.project.root_item.children}
    assert by_name == {
        "red_64x36.bmp": False,
        "renamed tone": False,
        "Seq A": True,
        "Seq B": True,
    }


def test_default_speed_and_reverse() -> None:
    # 06_api elides speed/reverse everywhere: normal speed, forward.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    for sequence in application.project.sequences:
        for track in sequence.video_tracks + sequence.audio_tracks:
            for clip in track.clips:
                assert clip.speed == 1.0
                assert clip.is_speed_reversed is False


def test_speed_and_reverse_from_resave() -> None:
    # Abstract Slideshow was retimed and reversed in Premiere.
    application = py_premiere.parse(
        require_sample(RESAVES / "Abstract Slideshow_resave.prproj")
    )
    speeds = []
    reversed_count = 0
    for sequence in application.project.sequences:
        for track in sequence.video_tracks + sequence.audio_tracks:
            for clip in track.clips:
                speeds.append(clip.speed)
                reversed_count += clip.is_speed_reversed
    assert any(s != 1.0 for s in speeds)
    assert all(s > 0 for s in speeds)
    assert reversed_count > 0


def test_mute_from_resave() -> None:
    # Light Streak Logo has some muted tracks and many audible ones.
    application = py_premiere.parse(
        require_sample(RESAVES / "Light Streak Logo_resave.prproj")
    )
    tracks = [
        track
        for sequence in application.project.sequences
        for track in sequence.video_tracks + sequence.audio_tracks
    ]
    muted = [t for t in tracks if t.is_muted]
    assert muted
    assert any(not t.is_muted for t in tracks)


def test_default_mute() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    for sequence in application.project.sequences:
        for track in sequence.video_tracks + sequence.audio_tracks:
            assert track.is_muted is False
