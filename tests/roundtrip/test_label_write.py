"""Writing a project item's color label: byte-fidelity + round-trip."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _bmp(application: py_premiere.models.Application) -> py_premiere.models.ProjectItem:
    return next(
        c for c in application.project.root_item.children if c.name == "red_64x36.bmp"
    )


def test_set_same_label_is_byte_identical(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "11_labels.prproj")
    item = _bmp(application)
    item.color_label = item.color_label  # bmp is FOREST (5)
    target = tmp_path / "same.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "11_labels.prproj").read_bytes()


def test_update_label_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "11_labels.prproj")
    _bmp(application).color_label = 10
    target = tmp_path / "updated.prproj"
    application.project.save(target)
    assert _bmp(parse_project_fresh(target)).color_label == 10


def test_clear_label_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "11_labels.prproj")
    _bmp(application).color_label = 0
    target = tmp_path / "cleared.prproj"
    application.project.save(target)
    assert _bmp(parse_project_fresh(target)).color_label == 0


def test_label_a_new_bin_round_trips(tmp_path) -> None:
    # A freshly-created bin has an empty property bag; labeling it exercises
    # the append-to-empty-bag path.
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")
    new_bin = application.project.root_item.add_bin("labeled")
    new_bin.color_label = 7
    target = tmp_path / "binned.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    reparsed = next(c for c in fresh.project.root_item.children if c.name == "labeled")
    assert reparsed.color_label == 7


def test_label_rejects_out_of_range() -> None:
    application = py_premiere.parse(MINIMAL / "11_labels.prproj")
    with pytest.raises(ValueError):
        _bmp(application).color_label = 16


def test_label_rejects_non_int() -> None:
    application = py_premiere.parse(MINIMAL / "11_labels.prproj")
    with pytest.raises(TypeError):
        _bmp(application).color_label = 5.0
