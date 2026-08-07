"""Validate parsed output against ExtendScript ground truth where present."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import sample_id, sample_prproj_paths

from py_premiere.cli.validate import validate_file

GROUND_TRUTH = [
    path for path in sample_prproj_paths() if path.with_suffix(".json").exists()
]


@pytest.mark.parametrize("path", GROUND_TRUTH, ids=[sample_id(p) for p in GROUND_TRUTH])
def test_matches_extendscript(path: Path) -> None:
    problems = validate_file(path, path.with_suffix(".json"))
    assert problems == []
