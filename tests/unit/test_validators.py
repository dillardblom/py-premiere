"""Unit tests for the validator factories."""

from __future__ import annotations

import pytest

from py_premiere.enums import ProjectItemType
from py_premiere.models.validators import (
    FLOAT32_MAX,
    validate_bool,
    validate_enum,
    validate_float32,
    validate_int,
    validate_marker_color_index,
    validate_number,
    validate_one_of,
    validate_path,
    validate_positive_number,
    validate_string,
)


def test_validate_number() -> None:
    validate_number(1.5)
    validate_number(2)
    with pytest.raises(TypeError):
        validate_number("1")
    with pytest.raises(TypeError):
        validate_number(True)
    with pytest.raises(ValueError, match="finite"):
        validate_number(float("nan"))
    with pytest.raises(ValueError, match=">= 0"):
        validate_positive_number(-1)


def test_validate_int_rejects_bool_and_float() -> None:
    validate_int(3)
    with pytest.raises(TypeError):
        validate_int(3.0)
    with pytest.raises(TypeError):
        validate_int(True)


def test_validate_string() -> None:
    validate_string()("ok")
    with pytest.raises(TypeError):
        validate_string()(1)
    with pytest.raises(ValueError, match="empty"):
        validate_string(allow_empty=False)("")
    with pytest.raises(ValueError, match="at most 3"):
        validate_string(max_length=3)("long")


def test_validate_enum() -> None:
    check = validate_enum(ProjectItemType)
    check(ProjectItemType.BIN)
    check(2)
    with pytest.raises(ValueError):
        check(99)
    with pytest.raises(TypeError):
        check(True)
    with pytest.raises(TypeError):
        check("BIN")


def test_validate_one_of() -> None:
    check = validate_one_of(["Video", "Audio"])
    check("Video")
    with pytest.raises(ValueError, match="must be one of"):
        check("Data")


def test_validate_bool() -> None:
    validate_bool(True)
    with pytest.raises(TypeError):
        validate_bool(1)


def test_validate_string_rejects_xml_illegal_control_characters() -> None:
    check = validate_string()
    check("plain")
    check("tab\there")
    check("line\nbreak")
    for illegal in ("nul\x00here", "\x01", "vertical\x0btab", "\x1f"):
        with pytest.raises(ValueError, match="control character"):
            check(illegal)


def test_validate_string_rejects_ambiguous_trailing_indent() -> None:
    check = validate_string()
    check("trailing\n")
    check("trailing\t")
    with pytest.raises(ValueError, match="newline followed by tabs"):
        check("trailing\n\t")
    with pytest.raises(ValueError, match="newline followed by tabs"):
        check("trailing\n\t\t")


def test_validate_string_rejects_unpaired_surrogates() -> None:
    with pytest.raises(ValueError, match="UTF-8"):
        validate_string()("\udc80")


def test_validate_marker_color_index_is_type_strict() -> None:
    validate_marker_color_index(0)
    validate_marker_color_index(7)
    with pytest.raises(ValueError, match="<= 7"):
        validate_marker_color_index(8)
    with pytest.raises(TypeError):
        validate_marker_color_index(True)
    with pytest.raises(TypeError):
        validate_marker_color_index(3.0)


def test_validate_float32_bounds() -> None:
    validate_float32(0.0)
    validate_float32(FLOAT32_MAX)
    with pytest.raises(ValueError):
        validate_float32(1e300)
    with pytest.raises(ValueError):
        validate_float32(-1e300)


def test_validate_path(tmp_path: object) -> None:
    validate_path()(str(tmp_path))
    with pytest.raises(TypeError):
        validate_path()(123)
    with pytest.raises(ValueError, match="does not exist"):
        validate_path(must_exist=True)(f"{tmp_path}/missing.prproj")
