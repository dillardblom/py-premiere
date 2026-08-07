"""Marker color writes: parity with Premiere's own `08_marker_colors`."""

from __future__ import annotations

import json
import re

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"

_GUID_KEY = re.compile(r"keywordExtDVAv1_[0-9a-f-]{36}")


def _blobs_by_guid(application: py_premiere.models.Application) -> dict[str, str]:
    out = {}
    for marker in application.project.sequences[0].markers:
        text = marker._blob().text or ""
        out[marker.guid] = _GUID_KEY.sub("keywordExtDVAv1_GUID", text)
    return out


def test_write_matches_premiere_output(tmp_path) -> None:
    """Setting the same colors py-side reproduces Premiere's 08 blobs.

    The cue-point GUID is random on both sides; normalized before compare.
    """
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    colors = {"comment": 1, "chapter": 4, "web": 6, "segment": 7}
    for marker in application.project.sequences[0].markers:
        marker.color_index = colors[marker.name]
    target = tmp_path / "colored.prproj"
    application.project.save(target)

    produced = _blobs_by_guid(parse_project_fresh(target))
    expected = _blobs_by_guid(py_premiere.parse(MINIMAL / "08_marker_colors.prproj"))
    assert produced == expected


def test_set_color_index_updates_in_place(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "08_marker_colors.prproj")
    markers = application.project.sequences[0].markers
    marker = next(m for m in markers if m.name == "comment")
    assert marker.color_index == 1
    marker.color_index = 5
    blob = json.loads(marker._blob().text)["DVAMarker"]
    # Overwrote the existing cue point rather than appending a second one.
    assert len(blob["mCuePointList"]) == 1
    target = tmp_path / "recolored.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_markers = fresh.project.sequences[0].markers
    fresh_marker = next(m for m in fresh_markers if m.name == "comment")
    assert fresh_marker.color_index == 5


def test_set_color_index_validates() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    marker = application.project.sequences[0].markers[0]
    with pytest.raises(ValueError):
        marker.color_index = 8
    with pytest.raises(ValueError):
        marker.color_index = -1
