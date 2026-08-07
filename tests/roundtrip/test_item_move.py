"""Moving project items between bins: byte-fidelity round-trip."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.enums import ProjectItemType

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _clip(root: py_premiere.models.ProjectItem) -> py_premiere.models.ProjectItem:
    return next(c for c in root.children if c.type is ProjectItemType.CLIP)


def test_move_into_new_bin_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    root = application.project.root_item
    destination = root.add_bin("dest")  # empty bin: Items list is synthesized
    clip = _clip(root)
    name = clip.name
    clip.move_to(destination)
    assert name not in {c.name for c in root.children}
    assert name in {c.name for c in destination.children}

    target = tmp_path / "moved.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_dest = next(c for c in fresh.project.root_item.children if c.name == "dest")
    assert name in {c.name for c in fresh_dest.children}


def test_nested_bin_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    outer = application.project.root_item.add_bin("outer")
    outer.add_bin("inner")  # add into a freshly-created (empty) bin
    target = tmp_path / "nested.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_outer = next(c for c in fresh.project.root_item.children if c.name == "outer")
    assert [c.name for c in fresh_outer.children] == ["inner"]


def test_move_back_to_root_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    root = application.project.root_item
    destination = root.add_bin("b")
    clip = _clip(root)
    name = clip.name
    clip.move_to(destination)
    clip.move_to(root)
    assert name in {c.name for c in root.children}
    assert name not in {c.name for c in destination.children}

    target = tmp_path / "back.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert name in {c.name for c in fresh.project.root_item.children}


def test_move_into_descendant_raises() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    root = application.project.root_item
    outer = root.add_bin("outer")
    inner = outer.add_bin("inner")
    with pytest.raises(ValueError):
        outer.move_to(inner)
    with pytest.raises(ValueError):
        outer.move_to(outer)


def test_move_into_another_project_is_refused() -> None:
    one = py_premiere.parse(MINIMAL / "02_bins.prproj")
    other = py_premiere.parse(MINIMAL / "02_bins.prproj")
    moving = next(c for c in one.project.root_item.children if c.name == "Bin A")
    with pytest.raises(ValueError, match="another project"):
        moving.move_to(other.project.root_item)
