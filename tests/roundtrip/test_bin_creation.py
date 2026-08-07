"""Bin creation: byte-fidelity round-trip."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.enums import ProjectItemType

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_add_bin_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    root = application.project.root_item
    before = len(root.children)

    new_bin = root.add_bin("py-bin")
    assert new_bin.type is ProjectItemType.BIN
    assert new_bin.name == "py-bin"
    assert len(root.children) == before + 1

    target = tmp_path / "with_bin.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    children = fresh.project.root_item.children
    bins = [c for c in children if c.type is ProjectItemType.BIN]
    assert [b.name for b in bins] == ["py-bin"]
    assert bins[0].children == []


def test_add_bin_is_idempotent(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    application.project.root_item.add_bin("b")
    first = tmp_path / "a.prproj"
    application.project.save(first)
    second = tmp_path / "b.prproj"
    parse_project_fresh(first).project.save(second)
    assert first.read_bytes() == second.read_bytes()


def test_add_bin_under_clip_raises() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    clip = next(
        c
        for c in application.project.root_item.children
        if c.type is ProjectItemType.CLIP
    )
    with pytest.raises(ValueError):
        clip.add_bin("nope")


def test_add_then_remove_bin_restores_original(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    root = application.project.root_item
    new_bin = root.add_bin("temp-bin")
    root.remove_bin(new_bin)
    target = tmp_path / "restored.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "06_api.prproj").read_bytes()


def test_remove_existing_empty_bin(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")
    root = application.project.root_item
    empty_bin = next(
        c for c in root.children if c.type is ProjectItemType.BIN and not c.children
    )
    name = empty_bin.name
    root.remove_bin(empty_bin)
    target = tmp_path / "removed.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert name not in {c.name for c in fresh.project.root_item.children}


def test_remove_populated_bin_is_recursive(tmp_path) -> None:
    # Premiere deletes a bin with its contents; py matches (verified via
    # pr-compare against Premiere's own removal of the same bin).
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")
    root = application.project.root_item
    populated = next(
        c for c in root.children if c.type is ProjectItemType.BIN and c.children
    )
    nested_uid = populated.children[0]._element.get("ObjectUID")
    root.remove_bin(populated)
    target = tmp_path / "recursive.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    names = {c.name for c in fresh.project.root_item.children}
    assert populated.name not in names
    assert nested_uid not in fresh.project._document.by_object_uid
