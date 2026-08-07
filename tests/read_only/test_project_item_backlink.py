"""TrackItem.project_item back-link, checked against UXP ground truth."""

from __future__ import annotations

import json

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _uxp_names(uxp_json: str) -> list[str]:
    data = json.loads((MINIMAL / uxp_json).read_text(encoding="utf-8"))
    names = []
    for sequence in data["sequences"]:
        for track in sequence["videoTracks"] + sequence["audioTracks"]:
            for clip in track["clips"]:
                names.append(clip["projectItemName"])
    return names


def _py_names(prproj: str) -> list[str]:
    application = py_premiere.parse(MINIMAL / prproj)
    names = []
    for sequence in application.project.sequences:
        for track in sequence.video_tracks + sequence.audio_tracks:
            for clip in track.clips:
                item = clip.project_item
                names.append(item.name if item is not None else None)
    return names


def test_project_item_names_match_uxp() -> None:
    # 07_transitions is 06_api + a transition; same item graph, and its
    # UXP export carries projectItemName per clip.
    assert _py_names("07_transitions.prproj") == _uxp_names("07_transitions.uxp.json")


def test_backlink_reports_renamed_source() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    audio_clip = application.project.sequences[0].audio_tracks[0].clips[0]
    # Track-item name is the subclip name; project_item is the panel item.
    assert audio_clip.name == "tone_440_1s.wav"
    assert audio_clip.project_item is not None
    assert audio_clip.project_item.name == "renamed tone"
    assert audio_clip.project_item is application.project.root_item.children[1]
