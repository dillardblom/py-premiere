"""Lumetri writes through the standard param setter (67 + resave gate)."""

from __future__ import annotations

from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _exposure(application: py_premiere.models.Application):
    lumetri = next(
        clip.components["Lumetri Color"]
        for sequence in application.project.sequences
        for clip in sequence.clips
        if "Lumetri Color" in clip.components
    )
    return next(p for p in lumetri.properties if p.display_name == "Exposure")


def test_lumetri_exposure_write_round_trips(tmp_path) -> None:
    # The scalar write the resave gate verified 2026-07-30: Premiere kept a
    # py-written Exposure=2.5 through open+resave without touching any
    # Lumetri param, and the `Blob` param is a 2-byte constant, not a state
    # cache - so the standard param setter is the whole write story.
    application = py_premiere.parse(MINIMAL / "67_lumetri_exposure.prproj")
    _exposure(application).value = 2.5
    target = tmp_path / "lumetri.prproj"
    application.project.save(target)
    assert _exposure(parse_project_fresh(target)).value == 2.5
