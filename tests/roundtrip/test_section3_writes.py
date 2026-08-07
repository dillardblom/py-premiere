"""Frame-rate/PAR overrides + scale-to-frame against the 68-70 fixtures."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"

#: Ticks per frame for the 12.5 fps override 68_rate_override stores.
_RATE_12_5 = 20321280000
#: The h264's native rate (25 fps) and its 50-frame native duration.
_NATIVE_RATE = 10160640000
_NATIVE_DURATION = 508032000000


def _interp(
    application: py_premiere.models.Application, fragment: str
) -> py_premiere.models.project_item.FootageInterpretation:
    item = next(c for c in application.project.root_item.children if fragment in c.name)
    interpretation = item.footage_interpretation
    assert interpretation is not None
    return interpretation


def test_clear_and_reset_rate_override_is_byte_identical(tmp_path) -> None:
    # Premiere's own override wrote the flag pair and rewrote the source
    # duration (50 frames x the new rate); clearing must restore the
    # native-rate duration and re-setting must reproduce the exact bytes.
    application = py_premiere.parse(MINIMAL / "68_rate_override.prproj")
    interpretation = _interp(application, "h264")
    assert interpretation.frame_rate == Time(_RATE_12_5)
    interpretation.frame_rate = None
    assert interpretation.frame_rate == Time(_NATIVE_RATE)
    assert interpretation._source.findtext("OriginalDuration") == str(_NATIVE_DURATION)
    interpretation.frame_rate = Time(_RATE_12_5)
    target = tmp_path / "same_rate.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "68_rate_override.prproj").read_bytes()


def test_clear_and_reset_par_override_is_byte_identical(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "69_par_override.prproj")
    interpretation = _interp(application, "prores")
    assert interpretation.pixel_aspect_ratio == 40 / 33
    interpretation.pixel_aspect_ratio = None
    assert interpretation.pixel_aspect_ratio == 1.0
    interpretation.pixel_aspect_ratio = (40, 33)
    target = tmp_path / "same_par.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "69_par_override.prproj").read_bytes()


def test_toggle_scale_to_frame_is_byte_identical(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "70_scale_to_frame.prproj")
    item = next(
        c for c in application.project.root_item.children if c.name == "red_64x36.bmp"
    )
    assert item.scale_to_frame_size is True
    item.scale_to_frame_size = False
    assert item.scale_to_frame_size is False
    item.scale_to_frame_size = True
    target = tmp_path / "same_scale.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "70_scale_to_frame.prproj").read_bytes()


def test_overrides_round_trip_on_fresh_media(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    application.project.import_files(
        [SAMPLES_DIR / "models" / "assets" / "bars_64x36_h264.mp4"]
    )
    interpretation = _interp(application, "h264")
    interpretation.frame_rate = Time(_RATE_12_5)
    interpretation.pixel_aspect_ratio = (40, 33)
    item = next(c for c in application.project.root_item.children if "h264" in c.name)
    item.scale_to_frame_size = True
    target = tmp_path / "fresh.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    fresh_interp = _interp(fresh, "h264")
    assert fresh_interp.frame_rate == Time(_RATE_12_5)
    assert fresh_interp.pixel_aspect_ratio == 40 / 33
    fresh_item = next(c for c in fresh.project.root_item.children if "h264" in c.name)
    assert fresh_item.scale_to_frame_size is True


def test_section3_validation() -> None:
    application = py_premiere.parse(MINIMAL / "68_rate_override.prproj")
    interpretation = _interp(application, "h264")
    with pytest.raises(ValueError, match="positive"):
        interpretation.frame_rate = Time(0)
    with pytest.raises(TypeError):
        interpretation.frame_rate = 25
    with pytest.raises(TypeError):
        interpretation.pixel_aspect_ratio = (40.0, 33)
    with pytest.raises(ValueError, match="positive"):
        interpretation.pixel_aspect_ratio = (0, 33)
    root = application.project.root_item
    with pytest.raises(TypeError):
        root.children["renamed tone"].scale_to_frame_size = 1
    with pytest.raises(ValueError, match="video clip"):
        root.children["renamed tone"].scale_to_frame_size = True
