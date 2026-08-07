"""Muting/unmuting a track: byte-fidelity + round-trip."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"
FIXTURE = MINIMAL / "13_track_mute.prproj"  # V1 muted by Premiere (setMute)


def test_mute_same_track_is_byte_identical(tmp_path) -> None:
    # Re-muting the already-muted V1 reproduces Premiere's exact bytes.
    application = py_premiere.parse(FIXTURE)
    v1 = application.project.sequences[0].video_tracks[0]
    assert v1.is_muted is True
    v1.is_muted = True
    target = tmp_path / "same.prproj"
    application.project.save(target)
    assert target.read_bytes() == FIXTURE.read_bytes()


def test_mute_unmuted_track_round_trips(tmp_path) -> None:
    application = py_premiere.parse(FIXTURE)
    application.project.sequences[0].video_tracks[1].is_muted = True
    target = tmp_path / "muted.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert fresh.project.sequences[0].video_tracks[1].is_muted is True


def test_unmute_track_round_trips(tmp_path) -> None:
    application = py_premiere.parse(FIXTURE)
    v1 = application.project.sequences[0].video_tracks[0]
    v1.is_muted = False
    target = tmp_path / "unmuted.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    reparsed = fresh.project.sequences[0].video_tracks[0]
    assert reparsed.is_muted is False
    assert reparsed._element.find("ClipTrack/Track/IsMuted") is None


def test_toggle_mute_is_idempotent() -> None:
    application = py_premiere.parse(FIXTURE)
    v2 = application.project.sequences[0].video_tracks[1]  # starts unmuted
    track_element = v2._element.find("ClipTrack/Track")
    snapshot = ET.tostring(track_element, encoding="unicode")
    v2.is_muted = True
    v2.is_muted = False
    assert ET.tostring(track_element, encoding="unicode") == snapshot


def test_mute_rejects_non_bool() -> None:
    application = py_premiere.parse(FIXTURE)
    with pytest.raises(TypeError):
        application.project.sequences[0].video_tracks[0].is_muted = 1


#: An audio track's mute lives on its mix-graph fader, not on the track:
#: `ClipTrack/Track/IsMuted` is ignored (and dropped) by Premiere there.
#: This fixture is 06_api with A1 muted through ExtendScript's own
#: `audioTracks[0].setMute(1)`, so it IS the ground truth for the shape.
AUDIO_FIXTURE = MINIMAL / "17_audio_mute.prproj"
UNMUTED_SOURCE = MINIMAL / "06_api.prproj"
NATIVE_MUTE_KEYFRAME = "-91445760000000000,true,0,0,0,0,0,0"


def test_reads_the_native_audio_mute() -> None:
    application = py_premiere.parse(AUDIO_FIXTURE)
    sequence = application.project.sequences[0]
    assert [t.is_muted for t in sequence.audio_tracks] == [True, False, False]
    assert [t.is_muted for t in sequence.video_tracks] == [False, False, False]


def test_py_audio_mute_reproduces_premieres_bytes(tmp_path) -> None:
    # py muting the same track must produce Premiere's own file.
    application = py_premiere.parse(UNMUTED_SOURCE)
    application.project.sequences[0].audio_tracks[0].is_muted = True
    param = application.project.sequences[0].audio_tracks[0]._audio_mute_param()
    assert param is not None
    assert param.findtext("StartKeyframe") == NATIVE_MUTE_KEYFRAME
    assert param.findtext("CurrentValue") == "true"
    # Never the track flag: Premiere discards that one on an audio track.
    assert (
        application.project.sequences[0]
        .audio_tracks[0]
        ._element.find("ClipTrack/Track/IsMuted")
        is None
    )


def test_audio_unmute_restores_the_unmuted_bytes(tmp_path) -> None:
    application = py_premiere.parse(AUDIO_FIXTURE)
    track = application.project.sequences[0].audio_tracks[0]
    track.is_muted = False
    track.is_muted = True
    target = tmp_path / "remuted.prproj"
    application.project.save(target)
    # Re-muting Premiere's own muted track reproduces its bytes exactly.
    assert target.read_bytes() == AUDIO_FIXTURE.read_bytes()


def test_audio_mute_round_trips(tmp_path) -> None:
    application = py_premiere.parse(UNMUTED_SOURCE)
    application.project.sequences[0].audio_tracks[0].is_muted = True
    target = tmp_path / "audio_muted.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert fresh.project.sequences[0].audio_tracks[0].is_muted is True
