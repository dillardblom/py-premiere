"""`Project.create_multicam_clip` against Premiere's own graph in 24."""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models.project_item import (
    _add_item_ref,
    _child_items,
    _detach_item_ref,
    item_container,
)
from py_premiere.xml.document import ReferenceIndex

MINIMAL = SAMPLES_DIR / "models" / "minimal"
ASSETS = SAMPLES_DIR / "models" / "assets"

_GUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _normalized(element: ET.Element) -> str:
    # Same volatile families as the merged-clip parity test: identifiers,
    # per-clip and per-track GUIDs, change counters and panel view state.
    text = ET.tostring(element, encoding="unicode").rstrip("\n\t")
    text = re.sub(r'Object(ID|Ref|UID|URef)="[^"]+"', r'Object\1="N"', text)
    text = re.sub(r"<ClipID>[^<]+</ClipID>", "<ClipID>N</ClipID>", text)
    text = re.sub(rf"<ID>{_GUID}</ID>", "<ID>N</ID>", text)
    text = re.sub(
        r"<MasterClipChangeVersion>\d+</MasterClipChangeVersion>",
        "<MasterClipChangeVersion>N</MasterClipChangeVersion>",
        text,
    )
    text = re.sub(
        r"\s*<project\.icon\.view\.grid\.order>[^<]*"
        r"</project\.icon\.view\.grid\.order>",
        "",
        text,
    )
    return text


def _session_normalized(element: ET.Element) -> str:
    # On top of `_normalized`'s families: 24, 78 and 79 store three
    # DIFFERENT track-bag/ID/NextTrackID patterns for the same operation,
    # proving those are UI-session bookkeeping - the bags are view state
    # Premiere writes only for touched tracks, and the counters are
    # allocation high-water marks whose only invariant is sitting past
    # every used id.
    element = copy.deepcopy(element)
    for track_core in element.findall("ClipTrack/Track"):
        node = track_core.find("Node")
        if node is not None:
            track_core.remove(node)
    text = _normalized(element)
    text = re.sub(
        r"<NextTrackID>\d+</NextTrackID>", "<NextTrackID>N</NextTrackID>", text
    )
    text = re.sub(r"<ID>\d+</ID>", "<ID>N</ID>", text)
    return text


def _closure_of(application: py_premiere.models.Application, name: str):
    project = application.project
    item = project.root_item.children[name]
    index = ReferenceIndex(project._document)
    owned = project._document.owned_objects(
        [item._element, item._master_element], index
    )
    return item, owned


def _strip_multicam(application: py_premiere.models.Application, name: str):
    # Remove a multicam item's closure and model state; the bin stays as it
    # was, so each test decides whether to dissolve it.
    project = application.project
    document = project._document
    item, owned = _closure_of(application, name)
    hidden_uid = item._sequence_uid
    root = project.root_item
    root_container = root._element.find("ProjectItemContainer")
    _detach_item_ref(root_container, item._element.get("ObjectUID") or "")
    for element in owned:
        document.remove_object(element)
    root._children.remove(item)
    hidden = next(s for s in project._sequences if s.sequence_id == hidden_uid)
    project._sequences.remove(hidden)
    project._items_by_master_uid = None
    project._items_by_sequence_uid = None
    return owned


def test_recreating_premieres_own_multicam_matches() -> None:
    application = py_premiere.parse(MINIMAL / "24_multicam.prproj")
    project = application.project
    document = project._document
    item, owned = _closure_of(application, "bars_64x36_h264.mp4Multicam")
    expected: dict[str, list[str]] = {}
    for element in owned:
        expected.setdefault(element.tag, []).append(_normalized(element))

    # Strip Premiere's multicam clip and dissolve its Processed Clips bin
    # back into the root.
    hidden_uid = item._sequence_uid
    root = project.root_item
    root_container = root._element.find("ProjectItemContainer")
    _detach_item_ref(root_container, item._element.get("ObjectUID") or "")
    for element in owned:
        document.remove_object(element)
    root._children.remove(item)
    hidden = next(s for s in project._sequences if s.sequence_id == hidden_uid)
    project._sequences.remove(hidden)
    bin_item = root.children["Processed Clips"]
    bin_container = item_container(bin_item._element)
    for angle in list(bin_item.children):
        _detach_item_ref(bin_container, angle._element.get("ObjectUID") or "")
        bin_item._children.remove(angle)
        _add_item_ref(_child_items(root_container), angle._element.get("ObjectUID"))
        angle._parent = root
        root._children.append(angle)
    _detach_item_ref(root_container, bin_item._element.get("ObjectUID") or "")
    document.remove_object(bin_item._element)
    root._children.remove(bin_item)
    project._items_by_master_uid = None
    project._items_by_sequence_uid = None

    video_item = root.children["bars_64x36_h264.mp4"]
    av_item = root.children["bars_64x36_av.mp4"]
    created = project.create_multicam_clip([video_item, av_item])
    assert created.name == "bars_64x36_h264.mp4Multicam"
    assert not created.is_merged_clip

    _, rebuilt = _closure_of(application, "bars_64x36_h264.mp4Multicam")
    actual: dict[str, list[str]] = {}
    for element in rebuilt:
        actual.setdefault(element.tag, []).append(_normalized(element))
    assert sorted(actual) == sorted(expected)
    for tag, serializations in actual.items():
        assert sorted(serializations) == sorted(expected[tag]), f"{tag} diverges"
    # The bin came back with both angles filed inside.
    new_bin = root.children["Processed Clips"]
    assert sorted(c.name for c in new_bin.children) == [
        "bars_64x36_av.mp4",
        "bars_64x36_h264.mp4",
    ]


def test_recreating_78_three_angles_matches() -> None:
    # 78_multicam_3angle: three angles (the AV one first), the short prores
    # angle keeps its own length while the sources span the longest.
    application = py_premiere.parse(MINIMAL / "78_multicam_3angle.prproj")
    project = application.project
    document = project._document
    _, owned = _closure_of(application, "bars_64x36_av.mp4Multicam")
    expected: dict[str, list[str]] = {}
    for element in owned:
        expected.setdefault(element.tag, []).append(_session_normalized(element))
    _strip_multicam(application, "bars_64x36_av.mp4Multicam")

    # Dissolve the bin so the rebuild recreates it.
    root = project.root_item
    root_container = root._element.find("ProjectItemContainer")
    bin_item = root.children["Processed Clips"]
    bin_container = item_container(bin_item._element)
    for angle in list(bin_item.children):
        _detach_item_ref(bin_container, angle._element.get("ObjectUID") or "")
        bin_item._children.remove(angle)
        _add_item_ref(_child_items(root_container), angle._element.get("ObjectUID"))
        angle._parent = root
        root._children.append(angle)
    _detach_item_ref(root_container, bin_item._element.get("ObjectUID") or "")
    document.remove_object(bin_item._element)
    root._children.remove(bin_item)

    av_item = root.children["bars_64x36_av.mp4"]
    prores_item = root.children["bars_64x36_prores.mov"]
    video_item = root.children["bars_64x36_h264.mp4"]
    created = project.create_multicam_clip([av_item, prores_item, video_item])
    assert created.name == "bars_64x36_av.mp4Multicam"

    _, rebuilt = _closure_of(application, "bars_64x36_av.mp4Multicam")
    actual: dict[str, list[str]] = {}
    for element in rebuilt:
        actual.setdefault(element.tag, []).append(_session_normalized(element))
    assert sorted(actual) == sorted(expected)
    for tag, serializations in actual.items():
        assert sorted(serializations) == sorted(expected[tag]), f"{tag} diverges"


def test_recreating_79_second_multicam_reuses_bin() -> None:
    # 79_two_multicams: a second multicam over an audio-only wav angle -
    # no Link, and the sources file into the EXISTING Processed Clips bin.
    application = py_premiere.parse(MINIMAL / "79_two_multicams.prproj")
    project = application.project
    _, owned = _closure_of(application, "bars_64x36_prores.movMulticam")
    expected: dict[str, list[str]] = {}
    for element in owned:
        expected.setdefault(element.tag, []).append(_session_normalized(element))
    _strip_multicam(application, "bars_64x36_prores.movMulticam")

    bin_item = project.root_item.children["Processed Clips"]
    prores_item = bin_item.children["bars_64x36_prores.mov"]
    audio_item = bin_item.children["tone_660_stereo.wav"]
    created = project.create_multicam_clip([prores_item, audio_item])
    assert created.name == "bars_64x36_prores.movMulticam"

    # Still exactly one bin, same membership - the angles never moved.
    bins = [c for c in project.root_item.children if c.name == "Processed Clips"]
    assert len(bins) == 1
    assert sorted(c.name for c in bins[0].children) == [
        "bars_64x36_av.mp4",
        "bars_64x36_h264.mp4",
        "bars_64x36_prores.mov",
        "tone_660_stereo.wav",
    ]
    _, rebuilt = _closure_of(application, "bars_64x36_prores.movMulticam")
    actual: dict[str, list[str]] = {}
    for element in rebuilt:
        actual.setdefault(element.tag, []).append(_session_normalized(element))
    assert sorted(actual) == sorted(expected)
    for tag, serializations in actual.items():
        assert sorted(serializations) == sorted(expected[tag]), f"{tag} diverges"


def test_create_multicam_clip_round_trips(tmp_path) -> None:
    application = py_premiere.new()
    project = application.project
    video_item, av_item = project.import_files(
        [ASSETS / "bars_64x36_h264.mp4", ASSETS / "bars_64x36_av.mp4"]
    )
    created = project.create_multicam_clip([video_item, av_item], name="Angles")
    assert created.name == "Angles"
    target = tmp_path / "multicam.prproj"
    project.save(target)

    fresh = parse_project_fresh(target)
    root = fresh.project.root_item
    item = root.children["Angles"]
    assert item._backing_sequence() is not None
    assert not item.is_merged_clip
    hidden = next(
        s for s in fresh.project.sequences if s.sequence_id == item._sequence_uid
    )
    assert len(hidden.video_tracks) == 2
    assert len(hidden.audio_tracks) == 1
    assert hidden.video_tracks[0].clips[0].end.ticks == 508032000000
    assert hidden.video_tracks[1].clips[0].end.ticks == 508032000000
    assert hidden.audio_tracks[0].clips[0].end.ticks == 508032000000
    assert sorted(c.name for c in root.children["Processed Clips"].children) == [
        "bars_64x36_av.mp4",
        "bars_64x36_h264.mp4",
    ]


def test_create_multicam_clip_refuses_wrong_sources() -> None:
    application = py_premiere.parse(MINIMAL / "24_multicam.prproj")
    bin_item = application.project.root_item.children["Processed Clips"]
    video_item = bin_item.children["bars_64x36_h264.mp4"]
    av_item = bin_item.children["bars_64x36_av.mp4"]
    with pytest.raises(ValueError, match="at least two"):
        application.project.create_multicam_clip([video_item])
    with pytest.raises(ValueError, match="audio"):
        application.project.create_multicam_clip([video_item, video_item])
    with pytest.raises(ValueError, match="only one angle"):
        application.project.create_multicam_clip([av_item, av_item])
