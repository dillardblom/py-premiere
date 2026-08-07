"""Sequence settings read-side: parity with the ES `getSettings` fields."""

from __future__ import annotations

import json

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_settings_match_es_ground_truth() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    settings = application.project.sequences[0].settings
    expected = json.loads((MINIMAL / "06_api.json").read_text(encoding="utf-8"))
    es = expected["sequences"][0]["settings"]
    assert settings.video_frame_size == (
        es["videoFrameWidth"],
        es["videoFrameHeight"],
    )
    assert str(settings.video_frame_rate.ticks) == es["videoFrameRate"]["ticks"]
    assert settings.audio_channel_count == es["audioChannelCount"]
    assert str(settings.audio_sample_rate.ticks) == es["audioSampleRate"]["ticks"]


def test_settings_bag_fields() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    settings = application.project.sequences[0].settings
    # The preset path embeds the editing-mode GUID; both read from the bag.
    assert settings.editing_mode in settings.preview_rendering_preset_path
    assert settings.max_bit_depth is False
    assert settings.max_render_quality is False
    assert settings.preview_frame_size == (64, 36)
    assert isinstance(settings.preview_codec, int)
