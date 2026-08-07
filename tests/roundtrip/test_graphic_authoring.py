"""Text-graphic authoring against 66_eg_text."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models.time import TICKS_PER_SECOND, Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"
_GUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _normalized(element: ET.Element) -> str:
    # Identifiers, per-clip GUIDs and payload hashes reallocate; the rest
    # must reproduce Premiere's serialization exactly.
    text = ET.tostring(element, encoding="unicode").rstrip("\n\t")
    text = re.sub(r'Object(ID|Ref|UID|URef)="[^"]+"', r'Object\1="N"', text)
    text = re.sub(rf'BinaryHash="{_GUID}"', 'BinaryHash="N"', text)
    text = re.sub(r"<ClipID>[^<]+</ClipID>", "<ClipID>N</ClipID>", text)
    return text


def _graphic_clip(application: py_premiere.models.Application):
    for sequence in application.project.sequences:
        for track in sequence.video_tracks:
            for clip in track.clips:
                if "Text" in clip.components:
                    return sequence, track, clip
    raise AssertionError("no text graphic in the project")


def _closure(application: py_premiere.models.Application, clip):
    document = application.project._document
    chain = document.resolve(
        clip._element.find("ClipTrackItem/ComponentOwner/Components")
    )
    component = clip.components["Text"]
    master = document.resolve(clip._subclip_element.find("MasterClip"))
    source = document.resolve(clip._clip_element.find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("VideoStream"))
    template = document.resolve(master.find("Clips/Clip"))
    logging = document.resolve(master.find("LoggingInfo"))
    groups = document.resolve(master.find("AudioClipChannelGroups"))
    return [
        clip._element,
        clip._subclip_element,
        clip._clip_element,
        chain,
        component._element,
        master,
        template,
        logging,
        groups,
        source,
        media,
        stream,
        *[p._element for p in component.properties],
    ]


def test_authored_graphic_matches_premieres_own() -> None:
    # Strip Premiere's own graphic and rebuild it with the same text: every
    # element must serialize identically (identifiers and payload hashes
    # aside).
    application = py_premiere.parse(MINIMAL / "66_eg_text.prproj")
    _, track, clip = _graphic_clip(application)
    expected = [_normalized(e) for e in _closure(application, clip)]
    duration = clip.end - clip.start

    # The fixture's Position is wherever the Type tool was clicked, so the
    # rebuild authors that same point.
    track.remove_clip(clip)
    created = track.add_graphic(
        "py",
        duration=duration,
        position=(0.27454546093940735, 0.44660192728042603),
    )
    actual = [_normalized(e) for e in _closure(application, created)]
    assert actual == expected


def test_add_graphic_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    track = sequence.video_tracks[0]
    created = track.add_graphic("hello py", start=Time(2 * TICKS_PER_SECOND))
    assert created.components["Text"].match_name == "AE.ADBE Text"
    source_text = next(
        p
        for p in created.components["Text"].properties
        if p.display_name == "Source Text"
    )
    assert source_text.text == "hello py"

    target = tmp_path / "graphic.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    _, _, fresh_clip = _graphic_clip(fresh)
    fresh_text = next(
        p
        for p in fresh_clip.components["Text"].properties
        if p.display_name == "Source Text"
    )
    assert fresh_text.text == "hello py"
    assert len(fresh_clip.components["Text"].properties) == 22
    # Five seconds at the sequence timebase, placed at two seconds.
    timebase = fresh.project.sequences[0].timebase
    assert fresh_clip.start.ticks == 2 * TICKS_PER_SECOND
    assert fresh_clip.duration.ticks == (5 * TICKS_PER_SECOND) // timebase * timebase
    # The graphic's master stays out of the project panel, as Premiere's does.
    assert "hello py" not in [c.name for c in fresh.project.root_item.children]


def test_authored_graphic_text_is_editable(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = application.project.sequences[0].video_tracks[0]
    created = track.add_graphic("first")
    source_text = next(
        p
        for p in created.components["Text"].properties
        if p.display_name == "Source Text"
    )
    source_text.text = "second"
    target = tmp_path / "edited.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    _, _, fresh_clip = _graphic_clip(fresh)
    fresh_text = next(
        p
        for p in fresh_clip.components["Text"].properties
        if p.display_name == "Source Text"
    )
    assert fresh_text.text == "second"


def test_add_graphic_validation() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    with pytest.raises(ValueError):
        sequence.video_tracks[0].add_graphic("")
    with pytest.raises(TypeError):
        sequence.video_tracks[0].add_graphic(None)
    with pytest.raises(ValueError):
        sequence.audio_tracks[0].add_graphic("nope")
