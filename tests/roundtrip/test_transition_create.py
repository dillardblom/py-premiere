"""Creating and removing transitions, against Premiere's own output.

The two fixtures were made by Premiere itself (through the QE DOM), so a
scoped `pr-compare` of py's transition against theirs is the parity bar.
"""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere import Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"
DISSOLVE = "ADBE Additive Dissolve"
#: The duration Premiere used for both fixtures (29 frames at 29.97).
FIXTURE_DURATION = 245794348800


def _seq_a(application: py_premiere.Application) -> py_premiere.Sequence:
    return next(s for s in application.project.sequences if s.name == "Seq A")


def test_head_transition_matches_premieres_own() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = _seq_a(application).video_tracks[0]
    transition = track.add_transition(
        track.clips[0], DISSOLVE, duration=Time(FIXTURE_DURATION)
    )
    expected = py_premiere.parse(MINIMAL / "07_transitions.prproj")
    theirs = _seq_a(expected).video_tracks[0].transitions[0]
    for attribute in ("name", "match_name", "has_incoming_clip", "has_outgoing_clip"):
        assert getattr(transition, attribute) == getattr(theirs, attribute)
    assert transition.start.ticks == theirs.start.ticks
    assert transition.end.ticks == theirs.end.ticks
    assert transition.cut_point_offset.ticks == theirs.cut_point_offset.ticks


def test_tail_transition_matches_premieres_own() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = _seq_a(application).video_tracks[0]
    transition = track.add_transition(
        track.clips[0], DISSOLVE, at_start=False, duration=Time(FIXTURE_DURATION)
    )
    expected = py_premiere.parse(MINIMAL / "27_transition_tail.prproj")
    theirs = _seq_a(expected).video_tracks[0].transitions[0]
    assert transition.start.ticks == theirs.start.ticks
    assert transition.end.ticks == theirs.end.ticks
    assert transition.cut_point_offset.ticks == theirs.cut_point_offset.ticks
    assert transition.has_outgoing_clip is True
    assert transition.has_incoming_clip is False


def test_transition_survives_a_disk_round_trip(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = _seq_a(application).video_tracks[0]
    track.add_transition(track.clips[0], DISSOLVE, duration=Time(FIXTURE_DURATION))
    target = tmp_path / "with_transition.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    transitions = _seq_a(fresh).video_tracks[0].transitions
    assert len(transitions) == 1
    assert transitions[0].match_name == DISSOLVE
    assert transitions[0].end.ticks == FIXTURE_DURATION
    # The clip carries the head reference Premiere writes.
    clip = _seq_a(fresh).video_tracks[0].clips[0]
    assert clip._element.find("ClipTrackItem/HeadTransition") is not None


def test_removing_restores_the_original_bytes(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = _seq_a(application).video_tracks[0]
    transition = track.add_transition(track.clips[0], DISSOLVE)
    track.remove_transition(transition)
    target = tmp_path / "removed.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "06_api.prproj").read_bytes()


def test_removing_premieres_transition_restores_the_base(tmp_path) -> None:
    # The other direction: dropping the transition Premiere made must leave
    # the file it was added to.
    application = py_premiere.parse(MINIMAL / "07_transitions.prproj")
    track = _seq_a(application).video_tracks[0]
    assert len(track.transitions) == 1
    track.remove_transition(track.transitions[0])
    target = tmp_path / "stripped.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    stripped = _seq_a(fresh).video_tracks[0]
    assert stripped.transitions == []
    assert stripped.clips[0]._element.find("ClipTrackItem/HeadTransition") is None


def test_rejects_what_it_cannot_do() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = _seq_a(application).video_tracks[0]
    clip = track.clips[0]
    with pytest.raises(ValueError, match="no verified display name"):
        track.add_transition(clip, "ADBE Nonexistent Wipe")
    # A whole frame longer: sub-frame overage is snapped away first.
    with pytest.raises(ValueError, match="longer than the clip"):
        track.add_transition(clip, DISSOLVE, duration=Time(clip.end.ticks + 8475667200))
    with pytest.raises(ValueError, match="positive duration"):
        track.add_transition(clip, DISSOLVE, duration=Time(0))
    other = application.project.sequences[1].video_tracks[0].clips[0]
    with pytest.raises(ValueError, match="not on this track"):
        track.add_transition(other, DISSOLVE)
    track.add_transition(clip, DISSOLVE)
    with pytest.raises(ValueError, match="already has a HeadTransition"):
        track.add_transition(clip, DISSOLVE)


def test_a_named_transition_needs_no_table_entry() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = _seq_a(application).video_tracks[0]
    transition = track.add_transition(
        track.clips[0], "ADBE Nonexistent Wipe", name="Nonexistent Wipe"
    )
    assert transition.name == "Nonexistent Wipe"
    assert transition.match_name == "ADBE Nonexistent Wipe"


def test_audio_transition_matches_premieres_own() -> None:
    # The audio class differs (`AudioTransitionTrackItem`, and it repeats the
    # clip's channel layout), so it needs its own parity check against the
    # crossfade Premiere made through the QE DOM.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = next(s for s in application.project.sequences if s.name == "Seq B")
    track = sequence.audio_tracks[0]
    transition = track.add_transition(
        track.clips[0], "Constant Power", duration=Time(508540032000)
    )
    expected = py_premiere.parse(MINIMAL / "31_audio_crossfade.prproj")
    theirs = next(
        t
        for s in expected.project.sequences
        for track_b in s.audio_tracks
        for t in track_b.transitions
    )
    assert transition.name == theirs.name
    assert transition.match_name == theirs.match_name
    assert transition.start.ticks == theirs.start.ticks
    assert transition.end.ticks == theirs.end.ticks
    layout = transition._element.findtext("AudioChannelLayout")
    assert layout == theirs._element.findtext("AudioChannelLayout")
    assert layout is not None


def test_audio_transition_copies_the_clips_channel_layout() -> None:
    # A mono clip has a different layout, and the transition must follow it
    # rather than assume stereo.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = _seq_a(application).audio_tracks[0]
    clip = track.clips[0]
    # That clip is shorter than the one-second default.
    transition = track.add_transition(
        clip, "Constant Power", duration=Time(FIXTURE_DURATION)
    )
    assert transition._element.findtext("AudioChannelLayout") == (
        clip._clip_element.findtext("AudioChannelLayout")
    )
    assert transition._element.findtext("AudioChannelLayout") == (
        '[{"channellabel":0}]'
    )


# --- transitions on a cut --------------------------------------------------

#: Each fixture is Premiere's own transition on a cut whose handles were
#: dialled to a known size before the edit (see
#: scripts/dev/make_cut_handle_bases.py): the clips are 20 frames each except
#: `roomy`, where nothing can clamp.
CUT_CASES = (
    "55_cut_both_wide",
    "56_cut_out_narrow",
    "57_cut_in_narrow",
    "58_cut_both_narrow",
    "59_cut_out_zero",
    "60_cut_roomy",
)
FRAME = 8475667200
#: Premiere's QE path used one second a side, rounded UP to 30 frames.
CUT_DURATION = 60 * FRAME
#: Premiere computes these spans in floating point and lands a few ticks off
#: the frame grid (`56` starts 5558 ticks after a clip that starts at 0). py
#: writes the frame-exact value, so allow that much and no more - it is six
#: millionths of a frame.
DRIFT = 6000


@pytest.mark.parametrize("fixture", CUT_CASES)
def test_cut_transition_clamping_matches_premiere(fixture: str) -> None:
    # Strip Premiere's own transition off the cut, put py's back, and the two
    # must agree: the halves are capped by the clip each covers and by the
    # OTHER clip's handle, since that one plays across the cut.
    application = py_premiere.parse(MINIMAL / f"{fixture}.prproj")
    sequence = _seq_a(application)
    track = sequence.video_tracks[1]
    assert len(track.transitions) == 1
    theirs = track.transitions[0]
    expected = (theirs.start.ticks, theirs.end.ticks, theirs.cut_point_offset.ticks)
    assert theirs.has_incoming_clip is True
    assert theirs.has_outgoing_clip is True

    track.remove_transition(theirs)
    assert track.transitions == []
    mine = track.add_transition(
        track.clips[0], DISSOLVE, at_start=False, duration=Time(CUT_DURATION)
    )
    for actual, want in zip(
        (mine.start.ticks, mine.end.ticks, mine.cut_point_offset.ticks), expected
    ):
        assert abs(actual - want) <= DRIFT
        assert actual % FRAME == 0


def test_cut_transition_is_double_sided() -> None:
    # A neighbour turns the same call into a cut transition, and BOTH clips
    # get a reference to the one object.
    application = py_premiere.parse(MINIMAL / "55_cut_both_wide.prproj")
    track = _seq_a(application).video_tracks[1]
    track.remove_transition(track.transitions[0])
    transition = track.add_transition(track.clips[0], DISSOLVE, at_start=False)
    assert transition.has_incoming_clip is True
    assert transition.has_outgoing_clip is True
    object_id = transition._element.get("ObjectID")
    outgoing = track.clips[0]._element.find("ClipTrackItem/TailTransition")
    incoming = track.clips[1]._element.find("ClipTrackItem/HeadTransition")
    assert outgoing is not None and outgoing.get("ObjectRef") == object_id
    assert incoming is not None and incoming.get("ObjectRef") == object_id


def test_removing_a_cut_transition_clears_both_clips() -> None:
    application = py_premiere.parse(MINIMAL / "55_cut_both_wide.prproj")
    track = _seq_a(application).video_tracks[1]
    track.remove_transition(track.transitions[0])
    for clip in track.clips:
        assert clip._element.find("ClipTrackItem/HeadTransition") is None
        assert clip._element.find("ClipTrackItem/TailTransition") is None


def test_no_handle_on_one_side_gives_a_one_sided_span() -> None:
    # `59` has a zero handle after the outgoing clip, so nothing can play
    # past the cut and the whole transition sits before it.
    application = py_premiere.parse(MINIMAL / "59_cut_out_zero.prproj")
    track = _seq_a(application).video_tracks[1]
    track.remove_transition(track.transitions[0])
    transition = track.add_transition(
        track.clips[0], DISSOLVE, at_start=False, duration=Time(CUT_DURATION)
    )
    assert transition.cut_point.ticks == track.clips[0].end.ticks
    assert transition.end.ticks == transition.cut_point.ticks
    assert transition.cut_point_offset.ticks == transition.duration.ticks


def test_a_cut_with_no_footage_either_side_is_refused() -> None:
    application = py_premiere.parse(MINIMAL / "59_cut_out_zero.prproj")
    track = _seq_a(application).video_tracks[1]
    track.remove_transition(track.transitions[0])
    # Pull the incoming clip's in point to zero: now neither clip can play
    # across the cut in either direction.
    track.clips[1].in_point = Time(0)
    track.clips[0].out_point = Time(track.clips[0].project_item._default_out_ticks or 0)
    with pytest.raises(ValueError, match="footage to play across the cut"):
        track.add_transition(track.clips[0], DISSOLVE, at_start=False)


def test_removing_a_transition_takes_its_component_with_it() -> None:
    # A newer transition owns a `VideoFilterComponent` and its parameters.
    # Leaving those behind is invisible in the parsed model but Premiere
    # garbage-collects them on resave, so the file would drift.
    application = py_premiere.parse(MINIMAL / "55_cut_both_wide.prproj")
    root = application.project._document.root
    before = len(list(root))
    track = _seq_a(application).video_tracks[1]
    transition = track.transitions[0]
    assert transition._element.find("VideoFilterComponent") is not None
    track.remove_transition(transition)
    # The transition plus everything only it referenced.
    assert len(list(root)) < before - 1
    assert not any(element.tag == "VideoTransitionTrackItem" for element in root)
    assert not any(
        (element.findtext("Name") or "") == "Transition Timing" for element in root
    )
