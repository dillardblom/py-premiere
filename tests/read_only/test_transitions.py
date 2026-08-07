"""Transition parsing against the three alignment fixtures."""

from __future__ import annotations

from pathlib import Path

from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.models.transition import Transition

MINIMAL = SAMPLES_DIR / "models" / "minimal"
FIXTURE = MINIMAL / "07_transitions.prproj"
TAIL = MINIMAL / "27_transition_tail.prproj"
CUT = MINIMAL / "30_transition_cut.prproj"
CROSSFADE = MINIMAL / "31_audio_crossfade.prproj"


def _only_transition(path: Path) -> Transition:
    application = py_premiere.parse(path)
    transitions = application.project.sequences[0].video_tracks[0].transitions
    assert len(transitions) == 1
    return transitions[0]


def test_transitions_parsed() -> None:
    application = py_premiere.parse(FIXTURE)
    sequence = application.project.sequences[0]
    track = sequence.video_tracks[0]
    assert len(track.transitions) == 1
    transition = track.transitions[0]
    # Values from the generating UXP call (ADBE Additive Dissolve applied
    # to the start of the first clip on V1) and the stored XML.
    assert transition.name == "Additive Dissolve (Legacy)"
    assert transition.match_name == "ADBE Additive Dissolve"
    assert transition.has_incoming_clip is True
    assert transition.has_outgoing_clip is False
    assert transition.start.ticks == 0
    assert transition.end.ticks == 245794348800
    assert transition.duration.ticks == 245794348800
    assert transition.track is track


def test_no_transitions_elsewhere() -> None:
    application = py_premiere.parse(FIXTURE)
    sequence = application.project.sequences[0]
    others = sequence.video_tracks[1:] + sequence.audio_tracks
    assert all(track.transitions == [] for track in others)


def test_head_transition_sits_after_its_cut() -> None:
    transition = _only_transition(FIXTURE)
    assert transition.cut_point_offset.ticks == 0
    assert transition.cut_point.ticks == transition.start.ticks


def test_tail_transition_sits_before_its_cut() -> None:
    # setApplyToStart(false) on the same clip: the whole transition is now
    # before the cut, so the stored offset is its full duration.
    transition = _only_transition(TAIL)
    assert transition.has_incoming_clip is False
    assert transition.has_outgoing_clip is True
    assert transition.cut_point_offset.ticks == transition.duration.ticks
    assert transition.cut_point.ticks == transition.end.ticks


def test_cut_transition_straddles_its_cut() -> None:
    # Applied to a real cut (two adjacent clips on V1), so both sides are
    # real and the offset lands strictly inside the transition. Premiere
    # clamped it to the handles the clips had, so it is NOT half.
    transition = _only_transition(CUT)
    assert transition.has_incoming_clip is True
    assert transition.has_outgoing_clip is True
    offset = transition.cut_point_offset.ticks
    assert 0 < offset < transition.duration.ticks
    assert offset != transition.duration.ticks // 2
    # The cut is the second clip's start, which is also the first's end.
    clips = py_premiere.parse(CUT).project.sequences[0].video_tracks[0].clips
    assert transition.cut_point.ticks == clips[1].start.ticks
    assert transition.cut_point.ticks == clips[0].end.ticks


def test_audio_crossfade_reads_like_a_video_transition() -> None:
    # `AudioTransitionTrackItem` shares the `TransitionTrackItem` base, so
    # the same model reads it - only its extra `AudioChannelLayout` differs,
    # and that is not part of the transition surface.
    application = py_premiere.parse(CROSSFADE)
    tracks = [
        track
        for sequence in application.project.sequences
        for track in sequence.audio_tracks
        if track.transitions
    ]
    assert len(tracks) == 1
    transition = tracks[0].transitions[0]
    assert transition.name == "Constant Power"
    assert transition.match_name == "Constant Power"
    assert transition.has_incoming_clip is True
    assert transition.has_outgoing_clip is False
    assert transition.start.ticks == 0
    assert transition.cut_point_offset.ticks == 0
    assert transition.end.ticks == 60 * 8475667200


def test_no_video_transition_in_the_crossfade_fixture() -> None:
    application = py_premiere.parse(CROSSFADE)
    assert all(
        track.transitions == []
        for sequence in application.project.sequences
        for track in sequence.video_tracks
    )
