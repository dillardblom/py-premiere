"""Essential Sound tagging against 65_essential_sound."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.xml.mutations import remove_child

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _tagged_clip(application: py_premiere.models.Application):
    for sequence in application.project.sequences:
        for track in sequence.audio_tracks:
            for clip in track.clips:
                if clip._element.find("ClipTrackItem/TrackItem") is not None:
                    return clip
    raise AssertionError("no audio track item in the project")


def test_recreating_premieres_dialogue_tag_matches() -> None:
    # Strip the fixture's own bag and re-tag: the TrackItem core must
    # serialize identically.
    application = py_premiere.parse(MINIMAL / "65_essential_sound.prproj")
    clip = next(
        c
        for s in application.project.sequences
        for t in s.audio_tracks
        for c in t.clips
        if c.essential_sound_tag == "dialog"
    )
    inner = clip._element.find("ClipTrackItem/TrackItem")
    expected = ET.tostring(inner, encoding="unicode")
    node = inner.find("Node")
    remove_child(inner, node)
    assert clip.essential_sound_tag is None

    clip.tag_as_dialogue()
    assert ET.tostring(inner, encoding="unicode") == expected
    assert clip.essential_sound_tag == "dialog"


def test_dialogue_tag_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    clip = _tagged_clip(application)
    assert clip.essential_sound_tag is None
    clip.tag_as_dialogue()
    with pytest.raises(ValueError):
        clip.tag_as_dialogue()
    target = tmp_path / "dialogue.prproj"
    application.project.save(target)
    fresh_clip = _tagged_clip(parse_project_fresh(target))
    assert fresh_clip.essential_sound_tag == "dialog"
