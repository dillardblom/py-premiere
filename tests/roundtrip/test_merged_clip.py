"""`Project.create_merged_clip` against Premiere's own graph in 23."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models.project_item import _detach_item_ref
from py_premiere.xml.document import ReferenceIndex

MINIMAL = SAMPLES_DIR / "models" / "minimal"
ASSETS = SAMPLES_DIR / "models" / "assets"

_GUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _normalized(element: ET.Element) -> str:
    # ObjectIDs/UIDs reallocate, per-clip and per-track GUIDs are random,
    # change counters are bumped by the UI, and py elides Premiere's
    # machine-local audio conform cache paths and the panel view state
    # stamp; everything else must serialize identically.
    text = ET.tostring(element, encoding="unicode").rstrip("\n\t")
    text = re.sub(r'Object(ID|Ref|UID|URef)="[^"]+"', r'Object\1="N"', text)
    text = re.sub(r"<ClipID>[^<]+</ClipID>", "<ClipID>N</ClipID>", text)
    text = re.sub(rf"<ID>{_GUID}</ID>", "<ID>N</ID>", text)
    text = re.sub(
        r"<MasterClipChangeVersion>\d+</MasterClipChangeVersion>",
        "<MasterClipChangeVersion>N</MasterClipChangeVersion>",
        text,
    )
    text = re.sub(r"\s*<(ConformedAudioPath|PeakFilePath)>[^<]*</\1>", "", text)
    text = re.sub(
        r"\s*<project\.icon\.view\.grid\.order>[^<]*"
        r"</project\.icon\.view\.grid\.order>",
        "",
        text,
    )
    return text


def _merged_closure(application: py_premiere.models.Application):
    project = application.project
    item = next(c for c in project.root_item.children if c.is_merged_clip)
    index = ReferenceIndex(project._document)
    owned = project._document.owned_objects(
        [item._element, item._master_element], index
    )
    return item, owned


def test_recreating_premieres_own_merged_clip_matches() -> None:
    application = py_premiere.parse(MINIMAL / "23_merged_clip.prproj")
    project = application.project
    document = project._document
    item, owned = _merged_closure(application)
    expected: dict[str, list[str]] = {}
    for element in owned:
        expected.setdefault(element.tag, []).append(_normalized(element))

    # Strip Premiere's merged clip: the panel entry, the 63-object closure
    # and the hidden sequence's model.
    hidden_uid = item._sequence_uid
    container = project.root_item._element.find("ProjectItemContainer")
    _detach_item_ref(container, item._element.get("ObjectUID") or "")
    for element in owned:
        document.remove_object(element)
    project.root_item._children.remove(item)
    hidden = next(s for s in project._sequences if s.sequence_id == hidden_uid)
    project._sequences.remove(hidden)
    project._items_by_master_uid = None
    project._items_by_sequence_uid = None

    video_item = project.root_item.children["bars_64x36_h264.mp4"]
    audio_item = project.root_item.children["tone_880_hp5.wav"]
    created = project.create_merged_clip(video_item, audio_item)
    assert created.is_merged_clip
    assert created.name == "bars_64x36_h264.mp4 - Merged"

    _, rebuilt = _merged_closure(application)
    actual: dict[str, list[str]] = {}
    for element in rebuilt:
        actual.setdefault(element.tag, []).append(_normalized(element))
    assert sorted(actual) == sorted(expected)
    for tag, serializations in actual.items():
        assert sorted(serializations) == sorted(expected[tag]), f"{tag} diverges"


def test_recreating_premieres_stereo_merged_clip_matches() -> None:
    # 77_merged_stereo: the stereo source lands as one MONO track per
    # channel over a single copied graph, channel-selected through
    # OrigChGrp/SecondaryIndex.
    application = py_premiere.parse(MINIMAL / "77_merged_stereo.prproj")
    project = application.project
    document = project._document
    item, owned = _merged_closure(application)
    expected: dict[str, list[str]] = {}
    for element in owned:
        expected.setdefault(element.tag, []).append(_normalized(element))

    hidden_uid = item._sequence_uid
    container = project.root_item._element.find("ProjectItemContainer")
    _detach_item_ref(container, item._element.get("ObjectUID") or "")
    for element in owned:
        document.remove_object(element)
    project.root_item._children.remove(item)
    hidden = next(s for s in project._sequences if s.sequence_id == hidden_uid)
    project._sequences.remove(hidden)
    project._items_by_master_uid = None
    project._items_by_sequence_uid = None

    video_item = project.root_item.children["bars_64x36_h264.mp4"]
    audio_item = project.root_item.children["tone_660_stereo.wav"]
    created = project.create_merged_clip(video_item, audio_item)
    assert created.is_merged_clip

    _, rebuilt = _merged_closure(application)
    actual: dict[str, list[str]] = {}
    for element in rebuilt:
        actual.setdefault(element.tag, []).append(_normalized(element))
    assert sorted(actual) == sorted(expected)
    for tag, serializations in actual.items():
        assert sorted(serializations) == sorted(expected[tag]), f"{tag} diverges"


def test_create_merged_clip_round_trips(tmp_path) -> None:
    application = py_premiere.new()
    project = application.project
    video_item, audio_item = project.import_files(
        [ASSETS / "bars_64x36_h264.mp4", ASSETS / "tone_880_hp5.wav"]
    )
    created = project.create_merged_clip(video_item, audio_item, name="Merged AV")
    assert created.name == "Merged AV"
    target = tmp_path / "merged.prproj"
    project.save(target)

    fresh = parse_project_fresh(target)
    item = next(c for c in fresh.project.root_item.children if c.is_merged_clip)
    assert item.name == "Merged AV"
    # The sources and the merged item share the panel; the copies have no
    # panel entry of their own.
    names = sorted(c.name for c in fresh.project.root_item.children)
    assert names == ["Merged AV", "bars_64x36_h264.mp4", "tone_880_hp5.wav"]
    hidden = next(
        s for s in fresh.project.sequences if s.sequence_id == item._sequence_uid
    )
    assert len(hidden.video_tracks) == 1
    assert len(hidden.audio_tracks) == 1
    video_clip = hidden.video_tracks[0].clips[0]
    audio_clip = hidden.audio_tracks[0].clips[0]
    # The video runs its 2 s; the 0.5 s audio floor-snaps to 12 whole video
    # frames, exactly as Premiere places it.
    assert video_clip.end.ticks == 508032000000
    assert audio_clip.end.ticks == 121927680000


def test_create_merged_clip_refuses_wrong_sources() -> None:
    application = py_premiere.parse(MINIMAL / "23_merged_clip.prproj")
    children = application.project.root_item.children
    video_item = children["bars_64x36_h264.mp4"]
    audio_item = children["tone_880_hp5.wav"]
    with pytest.raises(ValueError, match="video-only"):
        application.project.create_merged_clip(audio_item, audio_item)
    with pytest.raises(ValueError, match="video-only"):
        application.project.create_merged_clip(video_item, video_item)
