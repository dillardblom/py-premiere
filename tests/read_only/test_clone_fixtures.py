"""Sequence.clone / createSubsequence read-side, fixtures 73/74."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_cloned_sequence_reads_like_the_original() -> None:
    project = py_premiere.parse(MINIMAL / "73_clone.prproj").project
    original = project.sequences["Seq A"]
    copy = project.sequences["Seq A Copy"]
    assert [c.name for c in copy.clips] == [c.name for c in original.clips]
    assert len(copy.video_tracks) == len(original.video_tracks)
    # The clone gets its own panel item like any sequence.
    assert project.root_item.children["Seq A Copy"].is_sequence


def test_subsequence_reads_with_its_partial_contents() -> None:
    project = py_premiere.parse(MINIMAL / "74_subsequence.prproj").project
    sub = project.sequences["Seq A_Sub_01"]
    # createSubsequence carried the targeted video clip only.
    assert [c.name for c in sub.clips] == ["red_64x36.bmp"]
    assert project.root_item.children["Seq A_Sub_01"].is_sequence
