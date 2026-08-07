"""`SequenceSettings` writes: no-op byte parity + round-trips."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_resetting_stored_settings_is_byte_identical(tmp_path) -> None:
    # 49_seq_settings carries non-default preview settings (QE-written);
    # re-setting every stored value must reproduce Premiere's exact bytes.
    application = py_premiere.parse(MINIMAL / "49_seq_settings.prproj")
    for sequence in application.project.sequences:
        settings = sequence.settings
        if settings.editing_mode is not None:
            settings.editing_mode = settings.editing_mode
        settings.max_bit_depth = settings.max_bit_depth
        settings.max_render_quality = settings.max_render_quality
        if settings.preview_codec is not None:
            settings.preview_codec = settings.preview_codec
        if settings.preview_rendering_preset_path is not None:
            settings.preview_rendering_preset_path = (
                settings.preview_rendering_preset_path
            )
        if settings.preview_frame_size is not None:
            settings.preview_frame_size = settings.preview_frame_size
    target = tmp_path / "same.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "49_seq_settings.prproj").read_bytes()


def test_settings_round_trip(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    settings = application.project.sequences[0].settings
    settings.max_bit_depth = True
    settings.max_render_quality = True
    settings.preview_codec = 1634755443  # 'apcs'
    settings.preview_frame_size = (1280, 720)
    target = tmp_path / "changed.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target).project.sequences[0].settings
    assert fresh.max_bit_depth is True
    assert fresh.max_render_quality is True
    assert fresh.preview_codec == 1634755443
    assert fresh.preview_frame_size == (1280, 720)


def test_settings_validation() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    settings = application.project.sequences[0].settings
    with pytest.raises(TypeError):
        settings.max_bit_depth = 1
    with pytest.raises(TypeError):
        settings.preview_codec = "apcs"
    with pytest.raises(TypeError):
        settings.preview_frame_size = (1280.0, 720)
    with pytest.raises(ValueError):
        settings.preview_frame_size = (0, 720)
    with pytest.raises(TypeError):
        settings.editing_mode = 5
