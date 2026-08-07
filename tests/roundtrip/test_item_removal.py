"""Removing clip items from the panel: parity with Premiere's delete graph."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_remove_item_deletes_media_graph(tmp_path) -> None:
    # Premiere deletes 9 objects with 03_one_clip's bmp (item, master,
    # logging, template clip, channel groups, markers, source, media,
    # stream); verified via pr-compare against Premiere's own removal.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    root = application.project.root_item
    before = len(list(application.project._document.root))
    root.remove_item(root.children[0])
    after = len(list(application.project._document.root))
    assert before - after == 9

    target = tmp_path / "removed.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert fresh.project.root_item.children == []


def test_remove_item_in_use_raises() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    root = application.project.root_item
    bmp = next(c for c in root.children if c.name == "red_64x36.bmp")
    with pytest.raises(ValueError):
        root.remove_item(bmp)


def test_remove_item_after_clip_removal_works(tmp_path) -> None:
    # Removing the item's timeline clips first releases the in-use guard.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    v1 = sequence.video_tracks[0]
    v1.remove_clip(v1.clips[0])
    root = application.project.root_item
    bmp = next(c for c in root.children if c.name == "red_64x36.bmp")
    root.remove_item(bmp)
    target = tmp_path / "released.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert "red_64x36.bmp" not in {c.name for c in fresh.project.root_item.children}


def test_remove_sequence_item_raises() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    root = application.project.root_item
    sequence_item = next(c for c in root.children if c.is_sequence)
    with pytest.raises(ValueError):
        root.remove_item(sequence_item)


def test_remove_bin_holding_clip(tmp_path) -> None:
    # Bin removal cascades through remove_item for clip children.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    root = application.project.root_item
    bin_item = root.add_bin("doomed")
    root.children[0].move_to(bin_item)
    root.remove_bin(bin_item)
    target = tmp_path / "cascade.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert fresh.project.root_item.children == []
