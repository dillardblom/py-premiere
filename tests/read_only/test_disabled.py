"""TrackItem.is_disabled against the `12_disabled` fixture."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_disabled_clip() -> None:
    # The first V1 clip was disabled via UXP createSetDisabledAction.
    application = py_premiere.parse(MINIMAL / "12_disabled.prproj")
    clip = application.project.sequences[0].video_tracks[0].clips[0]
    assert clip.is_disabled is True


def test_enabled_clips_default_false() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    for sequence in application.project.sequences:
        for track in sequence.video_tracks + sequence.audio_tracks:
            for clip in track.clips:
                assert clip.is_disabled is False
