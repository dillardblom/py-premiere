"""Footage interpretation against the `15_footage_interp` fixture."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.enums import AlphaUsage, VideoFieldType

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_overridden_fields() -> None:
    # The sweep's final state: field type overridden to upper-first;
    # ignore/invert flags true but their values cleared (lingering flags),
    # frame rate value present without its flag (lingering value).
    application = py_premiere.parse(MINIMAL / "15_footage_interp.prproj")
    ghost = next(
        c for c in application.project.root_item.children if c.name == "ghost_16x9.png"
    )
    interpretation = ghost.footage_interpretation
    assert interpretation is not None
    assert interpretation.field_type is VideoFieldType.UPPER_FIRST
    assert interpretation.frame_rate.ticks == 8475667200
    # Alpha is not overridden here, so it reads NONE (matching ExtendScript,
    # which reports NONE regardless of the media's native AlphaType); the
    # ignore/invert flags linger without their values, so both read False.
    assert interpretation.alpha_usage is AlphaUsage.NONE
    assert interpretation.ignore_alpha is False
    assert interpretation.invert_alpha is False
    assert interpretation.pixel_aspect_ratio == 1.0


def test_defaults_without_overrides() -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    bmp = application.project.root_item.children[0]
    interpretation = bmp.footage_interpretation
    assert interpretation is not None
    assert interpretation.field_type is VideoFieldType.DEFAULT
    assert interpretation.alpha_usage is AlphaUsage.NONE
    assert interpretation.pixel_aspect_ratio == 1.0


def test_none_for_bins() -> None:
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")
    assert application.project.root_item.children[0].footage_interpretation is None


def test_write_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    interpretation = application.project.root_item.children[0].footage_interpretation
    interpretation.field_type = VideoFieldType.UPPER_FIRST
    interpretation.alpha_usage = AlphaUsage.PREMULTIPLIED
    interpretation.invert_alpha = True

    target = tmp_path / "interp.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    reparsed = fresh.project.root_item.children[0].footage_interpretation
    assert reparsed.field_type is VideoFieldType.UPPER_FIRST
    assert reparsed.alpha_usage is AlphaUsage.PREMULTIPLIED
    assert reparsed.invert_alpha is True


def test_overrides_land_at_schema_positions() -> None:
    # A newly written override sits at its canonical VideoStream position
    # (before FieldTypeIsUncertain, after AlphaType), matching Premiere.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    interpretation = application.project.root_item.children[0].footage_interpretation
    interpretation.alpha_usage = AlphaUsage.PREMULTIPLIED
    tags = [child.tag for child in interpretation._stream]
    assert tags.index("IsAlphaTypeOverridden") > tags.index("AlphaType")
    assert tags.index("OverriddenAlphaType") < tags.index("FieldTypeIsUncertain")


def test_reset_to_default_clears_override(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    interpretation = application.project.root_item.children[0].footage_interpretation
    interpretation.field_type = VideoFieldType.LOWER_FIRST
    interpretation.field_type = VideoFieldType.DEFAULT
    assert interpretation._stream.find("IsFieldTypeOverridden") is None
    assert interpretation._stream.find("OverriddenFieldType") is None
    assert interpretation.field_type is VideoFieldType.DEFAULT


def test_write_rejects_bad_enum() -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    interpretation = application.project.root_item.children[0].footage_interpretation
    with pytest.raises(ValueError):
        interpretation.field_type = 99  # type: ignore[assignment]


def test_pixel_aspect_ratio_accepts_what_it_returns() -> None:
    # The getter derives a float; the setter used to demand the exact pair,
    # so the property could not round-trip its own value.
    application = py_premiere.parse(MINIMAL / "69_par_override.prproj")
    for item in application.project.root_item.walk():
        interpretation = item.footage_interpretation
        if interpretation is None:
            continue
        value = interpretation.pixel_aspect_ratio
        interpretation.pixel_aspect_ratio = value
        assert interpretation.pixel_aspect_ratio == value


def test_pixel_aspect_ratio_round_trip_is_byte_identical() -> None:
    source = MINIMAL / "69_par_override.prproj"
    application = py_premiere.parse(source)
    for item in application.project.root_item.walk():
        interpretation = item.footage_interpretation
        if interpretation is not None:
            interpretation.pixel_aspect_ratio = interpretation.pixel_aspect_ratio
    assert application.project._document.to_bytes() == source.read_bytes()


def test_frame_rate_round_trip_on_a_still() -> None:
    # A still's duration is the 12-hour phantom span, which is no whole
    # number of frames - the setter must not refuse on that account.
    source = MINIMAL / "68_rate_override.prproj"
    application = py_premiere.parse(source)
    touched = 0
    for item in application.project.root_item.walk():
        interpretation = item.footage_interpretation
        if interpretation is None:
            continue
        interpretation.frame_rate = interpretation.frame_rate
        touched += 1
    assert touched
    assert application.project._document.to_bytes() == source.read_bytes()
