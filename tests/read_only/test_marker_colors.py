"""Marker color reading against the `08_marker_colors` fixture."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _markers(path: str) -> list[py_premiere.models.Marker]:
    application = py_premiere.parse(MINIMAL / path)
    return application.project.sequences[0].markers


def test_stored_colors() -> None:
    # The generating UXP call applied 1, 4, 6, 7 in time order; py yields
    # stored-XML order, so key by name.
    markers = _markers("08_marker_colors.prproj")
    by_name = {m.name: m.color_index for m in markers}
    assert by_name == {"comment": 1, "chapter": 4, "web": 6, "segment": 7}


def test_default_colors_by_type() -> None:
    # Uncolored markers report their type default (UXP getColorIndex).
    markers = _markers("06_api.prproj")
    by_type = {m.type: m.color_index for m in markers}
    assert by_type == {
        "Comment": 0,
        "Chapter": 1,
        "WebLink": 3,
        "Segmentation": 2,
    }
