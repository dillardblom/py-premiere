"""Audio component parsing against the `10_audio_volume` fixture."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR

import py_premiere

FIXTURE = SAMPLES_DIR / "models" / "minimal" / "10_audio_volume.prproj"


def _volume_component() -> py_premiere.models.Component:
    application = py_premiere.parse(FIXTURE)
    clip = application.project.sequences[0].audio_tracks[0].clips[0]
    assert len(clip.components) == 1
    return clip.components[0]


def test_audio_match_name() -> None:
    # Audio filter components store the identifier as FilterMatchName, which
    # ExtendScript also reports as the match name.
    assert _volume_component().match_name == "Internal Volume Mono"


def test_audio_level_value() -> None:
    # Level was set to 0.35 via UXP; ES getValue reports 0.34999999403954.
    # py reads the stored float32 string, agreeing to float precision.
    component = _volume_component()
    level = next(p for p in component.properties if p.display_name == "Level")
    assert level.value == pytest.approx(0.34999999403954)
