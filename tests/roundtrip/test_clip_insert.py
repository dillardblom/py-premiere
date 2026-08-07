"""Placing a clip on a track: byte-fidelity round-trip."""

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


def test_add_clip_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]  # Seq A
    v2 = sequence.video_tracks[1]
    assert v2.clips == []

    placed = v2.add_clip(_bmp(application))
    assert placed.name == "red_64x36.bmp"
    assert [c.name for c in v2.clips] == ["red_64x36.bmp"]

    target = tmp_path / "placed.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_v2 = fresh.project.sequences[0].video_tracks[1]
    assert [c.name for c in fresh_v2.clips] == ["red_64x36.bmp"]
    # The placed clip resolves back to the same project item.
    assert fresh_v2.clips[0].project_item is not None
    assert fresh_v2.clips[0].project_item.name == "red_64x36.bmp"


def test_add_clip_gets_fresh_clip_id(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    source = sequence.video_tracks[0].clips[0]
    source_clip_id = source._clip_element.findtext("Clip/ClipID")

    placed = sequence.video_tracks[1].add_clip(_bmp(application))
    assert placed._clip_element.findtext("Clip/ClipID") != source_clip_id


def test_add_clip_at_offset(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    item = _bmp(application)
    # A fresh placement plays the item's panel marks (in to out), exactly as
    # Premiere's own overwrite does - NOT the duration of an existing
    # timeline instance.
    duration = item.out_point.ticks - item.in_point.ticks
    placed = sequence.video_tracks[1].add_clip(item, start=Time(sequence.timebase))
    assert placed.start.ticks == sequence.timebase
    assert placed.end.ticks == sequence.timebase + duration

    target = tmp_path / "offset.prproj"
    application.project.save(target)
    fresh_clip = (
        parse_project_fresh(target).project.sequences[0].video_tracks[1].clips[0]
    )
    assert fresh_clip.start.ticks == sequence.timebase


def test_add_audio_clip_round_trips(tmp_path) -> None:
    # The wav master has no panel marks; unmarked finite media plays from 0,
    # trimmed down to whole sequence frames - the same 29-frame duration
    # Premiere's own placement of this wav stores in the fixture.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    item = next(
        c
        for c in application.project.root_item.children
        if c.media_path is not None and c.media_path.suffix == ".wav"
    )
    placed = sequence.audio_tracks[1].add_clip(item)
    premiere_placed = sequence.audio_tracks[0].clips[0]
    assert placed.duration.ticks == premiere_placed.duration.ticks

    target = tmp_path / "audio.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_a2 = fresh.project.sequences[0].audio_tracks[1]
    assert len(fresh_a2.clips) == 1
    assert fresh_a2.clips[0].duration.ticks == premiere_placed.duration.ticks


def test_first_placement_after_removal(tmp_path) -> None:
    # Synthesis is instance-independent: removing the only timeline instance
    # and placing the item again works (a true first placement).
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    v1 = sequence.video_tracks[0]
    v1.remove_clip(v1.clips[0])
    item = _bmp(application)
    placed = sequence.video_tracks[1].add_clip(item)
    assert placed.name == "red_64x36.bmp"

    target = tmp_path / "first.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_seq = fresh.project.sequences[0]
    assert fresh_seq.video_tracks[0].clips == []
    assert [c.name for c in fresh_seq.video_tracks[1].clips] == ["red_64x36.bmp"]


def test_add_clip_does_not_inherit_instance_state(tmp_path) -> None:
    # The old clone-based add_clip leaked the source instance's disabled
    # flag; a fresh placement must be enabled.
    application = py_premiere.parse(MINIMAL / "12_disabled.prproj")
    sequence = application.project.sequences[0]
    assert sequence.video_tracks[0].clips[0].is_disabled is True
    placed = sequence.video_tracks[1].add_clip(_bmp(application))
    assert placed.is_disabled is False


def test_add_unplaced_item_raises() -> None:
    # 02_bins has clips that are inside bins but not on any timeline.
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")

    def walk(item):
        yield item
        for child in item.children:
            yield from walk(child)

    clips = [
        i
        for i in walk(application.project.root_item)
        if i.type is py_premiere.enums.ProjectItemType.CLIP
    ]
    if not clips:
        pytest.skip("no clip items in fixture")
    sequence = application.project.sequences[0]
    with pytest.raises(NotImplementedError):
        sequence.video_tracks[0].add_clip(clips[0])


def test_add_clip_rejects_a_non_time_start_without_mutating() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    document = application.project._document
    before = document.to_bytes()
    track = application.project.sequences[0].video_tracks[1]
    with pytest.raises(TypeError):
        track.add_clip(_bmp(application), 0)
    # A refused placement must not leave its objects behind.
    assert document.to_bytes() == before


def test_insert_clip_rejects_a_non_time_start() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    with pytest.raises(TypeError):
        application.project.sequences[0].video_tracks[1].insert_clip(
            _bmp(application), 0
        )


def test_add_clip_refuses_to_nest_a_sequence_in_itself() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    own_item = sequence.project_item
    assert own_item is not None
    with pytest.raises(ValueError, match="own timeline"):
        sequence.video_tracks[1].add_clip(own_item, Time(0))
