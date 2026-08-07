"""Enabling/disabling a clip: byte-fidelity + round-trip."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _clips(application: py_premiere.models.Application) -> list:
    sequence = application.project.sequences[0]
    clips = []
    for track in sequence.video_tracks + sequence.audio_tracks:
        clips.extend(track.clips)
    return clips


def test_disable_same_clip_is_byte_identical(tmp_path) -> None:
    # 12_disabled already has a disabled clip; re-disabling it is a no-op
    # that must reproduce Premiere's exact bytes.
    application = py_premiere.parse(MINIMAL / "12_disabled.prproj")
    next(c for c in _clips(application) if c.is_disabled).is_disabled = True
    target = tmp_path / "same.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "12_disabled.prproj").read_bytes()


def test_disable_enabled_clip_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "12_disabled.prproj")
    clip = next(c for c in _clips(application) if not c.is_disabled)
    name = clip.name
    clip.is_disabled = True
    target = tmp_path / "disabled.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert next(c for c in _clips(fresh) if c.name == name).is_disabled is True


def test_enable_disabled_clip_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "12_disabled.prproj")
    clip = next(c for c in _clips(application) if c.is_disabled)
    name = clip.name
    clip.is_disabled = False
    target = tmp_path / "enabled.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    reparsed = next(c for c in _clips(fresh) if c.name == name)
    assert reparsed.is_disabled is False
    assert reparsed._element.find("ClipTrackItem/IsMuted") is None


def test_toggle_disable_is_idempotent(tmp_path) -> None:
    # Disable then enable returns to the original enabled bytes.
    application = py_premiere.parse(MINIMAL / "12_disabled.prproj")
    clip = next(c for c in _clips(application) if not c.is_disabled)
    original = clip._element.find("ClipTrackItem")
    snapshot = ET.tostring(original, encoding="unicode")
    clip.is_disabled = True
    clip.is_disabled = False
    assert ET.tostring(original, encoding="unicode") == snapshot


def test_disable_rejects_non_bool() -> None:
    application = py_premiere.parse(MINIMAL / "12_disabled.prproj")
    with pytest.raises(TypeError):
        _clips(application)[0].is_disabled = 1
