"""Lumetri Color decodes through the standard param machinery (67)."""

from __future__ import annotations

import json
import struct

import pytest
from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.models import Component

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_lumetri_exposure_reads_as_a_plain_param() -> None:
    # 67_lumetri_exposure: Basic Correction > Exposure = +1.0. Lumetri is
    # NOT an opaque blob - it stores ~90 ordinary named component params
    # (plus a `Blob` cache param), so the existing param API reads it.
    application = py_premiere.parse(MINIMAL / "67_lumetri_exposure.prproj")
    lumetri = next(
        clip.components["Lumetri Color"]
        for sequence in application.project.sequences
        for clip in sequence.clips
        if "Lumetri Color" in clip.components
    )
    assert lumetri.match_name == "AE.ADBE Lumetri"
    exposure = next(p for p in lumetri.properties if p.display_name == "Exposure")
    assert exposure.value == 1.0
    contrast = next(p for p in lumetri.properties if p.display_name == "Contrast")
    assert contrast.value == 0.0


def _lumetri() -> tuple[py_premiere.Application, Component]:
    application = py_premiere.parse(MINIMAL / "67_lumetri_exposure.prproj")
    component = next(
        clip.components["Lumetri Color"]
        for sequence in application.project.sequences
        for clip in sequence.clips
        if "Lumetri Color" in clip.components
    )
    return application, component


def _payload(
    application: py_premiere.Application, component: Component, name: str
) -> bytes | None:
    param = next(p for p in component.properties if p.display_name == name)
    value = param._element.find("StartKeyframeValue")
    return application.project._document.payload(value)


def test_auto_tone_analytics_reads_as_json() -> None:
    # One of Lumetri's arbitrary-data params is plain UTF-16 JSON, which
    # the existing `text` decode already reaches.
    application, lumetri = _lumetri()
    param = next(
        p for p in lumetri.properties if p.display_name == "Auto Tone Analytics Data"
    )
    data = json.loads(param.text)
    assert data["mAutoTonePressed"] is False
    assert data["mExposure"] == 0


@pytest.mark.parametrize(
    "name",
    ["Blob", "Embedded LUTs", "LUTAsset", "LookAsset", "Media Embedded Lut blob"],
)
def test_empty_asset_slots_store_the_two_byte_sentinel(name: str) -> None:
    # Lumetri's asset slots are not opaque data: with no LUT or Look
    # applied every one of them holds the same two bytes, which is how an
    # EMPTY slot is written. `Blob` in particular is not a cache of the
    # effect's state - it is empty here while Exposure is +1.0.
    application, lumetri = _lumetri()
    assert _payload(application, lumetri, name) == b"\xfe\xfe"


@pytest.mark.parametrize(
    ("name", "leading"),
    [
        ("Hue vs Sat", 3),
        ("Hue vs Hue", 3),
        ("Hue vs Luma", 3),
        ("Luma vs Sat", 2),
        ("Sat vs Sat", 2),
    ],
)
def test_curve_payload_layout(name: str, leading: int) -> None:
    # Every curve is a fixed 520-byte record: two little-endian uint32
    # (the second always zero) then 32 (x, y) float64 pairs. Untouched,
    # each holds the identity pair (1.0, 1.0) at index 1 and zeros after.
    # The leading word is NOT the point count - it is 3 for the hue-keyed
    # curves and 2 for the others while both store the same two pairs - so
    # it stays unnamed until an edited-curve fixture pins it.
    application, lumetri = _lumetri()
    payload = _payload(application, lumetri, name)
    assert len(payload) == 520
    first, second = struct.unpack_from("<II", payload, 0)
    assert (first, second) == (leading, 0)
    pairs = struct.unpack_from("<64d", payload, 8)
    points = list(zip(pairs[0::2], pairs[1::2]))
    assert len(points) == 32
    assert points[0] == (0.0, 0.0)
    assert points[1] == (1.0, 1.0)
    assert not any(any(point) for point in points[2:])
