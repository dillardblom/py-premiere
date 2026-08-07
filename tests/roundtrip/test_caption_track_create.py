"""`Sequence.create_caption_track` against Premiere's own track in 29."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.enums import CaptionFormat
from py_premiere.xml.document import ReferenceIndex
from py_premiere.xml.mutations import remove_child

MINIMAL = SAMPLES_DIR / "models" / "minimal"
SRT = SAMPLES_DIR / "models" / "assets" / "two_lines.srt"


def _normalized(element: ET.Element) -> str:
    # ObjectIDs/UIDs reallocate, per-clip GUIDs and the synthetic media's
    # modification blob are random, and the outer tail is document
    # position; everything else must serialize identically.
    text = ET.tostring(element, encoding="unicode").rstrip("\n\t")
    text = re.sub(r'Object(ID|Ref|UID|URef)="[^"]+"', r'Object\1="N"', text)
    text = re.sub(r"<ClipID>[^<]+</ClipID>", "<ClipID>N</ClipID>", text)
    return text


def _track_closure(
    application: py_premiere.models.Application,
) -> tuple[ET.Element, list[ET.Element]]:
    document = application.project._document
    track = next(
        element for element in document.root if element.tag == "CaptionDataClipTrack"
    )
    index = ReferenceIndex(document)
    return track, document.owned_objects([track], index)


def test_recreating_premieres_own_track_matches() -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    document = application.project._document
    track, owned = _track_closure(application)
    expected: dict[str, list[str]] = {}
    for element in owned:
        expected.setdefault(element.tag, []).append(_normalized(element))

    # Strip Premiere's track: the objects, the group's Tracks entry and
    # the bumped NextTrackID.
    sequence = next(s for s in application.project.sequences if s.caption_tracks)
    group_pair = next(
        pair
        for pair in sequence._element.findall("TrackGroups/TrackGroup")
        if pair.findtext("First") == "d8143ffe-eec4-4d2a-a909-d5f7bf094dc5"
    )
    group = document.resolve(group_pair.find("Second"))
    inner = group.find("TrackGroup")
    remove_child(inner, inner.find("Tracks"))
    inner.find("NextTrackID").text = "1"
    for element in owned:
        document.remove_object(element)
    sequence._caption_tracks.clear()

    item = application.project.root_item.children["two_lines.srt"]
    # The fixture's track is CEA-708; the API default is Subtitle.
    created = sequence.create_caption_track(item, CaptionFormat.CEA_708)
    _, rebuilt = _track_closure(application)
    actual: dict[str, list[str]] = {}
    for element in rebuilt:
        actual.setdefault(element.tag, []).append(_normalized(element))
    assert sorted(actual) == sorted(expected)
    for tag, serializations in actual.items():
        assert serializations == expected[tag], f"{tag} diverges"
    assert len(created.captions) == 2


def test_create_caption_track_round_trips(tmp_path) -> None:
    # End to end on py's own SRT import in a virgin sequence.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    item = application.project.import_files([SRT])[0]
    sequence = application.project.sequences[0]
    track = sequence.create_caption_track(item)
    assert [c.text for c in track.captions] == [
        "Hello from py-premiere",
        "Second caption line",
    ]
    target = tmp_path / "captioned.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    fresh_track = fresh.project.sequences[0].caption_tracks[0]
    captions = fresh_track.captions
    assert [c.text for c in captions] == [
        "Hello from py-premiere",
        "Second caption line",
    ]
    # Timeline times frame-snap to the sequence timebase (30/60 frames at
    # 29.97); source times stay exact.
    timebase = fresh.project.sequences[0].timebase
    assert captions[0].end.ticks == 30 * timebase
    assert captions[1].start.ticks == 30 * timebase
    assert captions[1].end.ticks == 60 * timebase
    assert captions[0].source_end.ticks == 254016000000


def test_create_caption_track_refuses_non_caption_items() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    with pytest.raises(ValueError, match="caption"):
        sequence.create_caption_track(application.project.root_item.children[0])
