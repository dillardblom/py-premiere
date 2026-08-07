"""Shared helpers for py_premiere tests (import with `from helpers import ...`)."""

from __future__ import annotations

from pathlib import Path

import pytest

import py_premiere

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def parse_project_fresh(path: Path) -> py_premiere.models.Application:
    """Re-parse from disk; use after `save` in roundtrip tests."""
    return py_premiere.parse(path)


def require_sample(path: Path) -> Path:
    """Skip the test when `path` is a local-only (uncommitted) sample.

    Only `samples/models/` is committed; resaves/templates are local-only,
    so tests that exercise them are skipped on a fresh checkout (CI).
    """
    if not path.exists():
        pytest.skip(f"local-only sample not present: {path.name}")
    return path


#: Local scratch areas (see .gitignore) whose contents must never leak into
#: the suites - they may hold deliberately broken or non-Adobe files. `refs`
#: holds Premiere reference output for pr-compare, including probe exports
#: whose values are deliberately captured mid-flight (a freshly opened
#: project reports movie media offline until linking settles).
_SCRATCH_DIRS = {"debug", "unused", "roundtrip", "effects", "refs"}


def sample_prproj_paths() -> list[Path]:
    """All local `.prproj` fixtures; empty on checkouts without samples (CI)."""
    paths = []
    for path in sorted(SAMPLES_DIR.rglob("*.prproj")):
        parents = {part.lower() for part in path.relative_to(SAMPLES_DIR).parts[:-1]}
        if not parents & _SCRATCH_DIRS:
            paths.append(path)
    return paths


def sample_id(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"


#: Decorator parametrizing a test over every local sample (skips when none).
each_sample = pytest.mark.parametrize("path", sample_prproj_paths(), ids=sample_id)


def first_mismatch(produced: bytes, expected: bytes, context: int = 32) -> str:
    """Compact description of the first differing offset between two byte strings."""
    if len(produced) != len(expected):
        note = f"length {len(produced)} != {len(expected)}"
    else:
        note = f"length {len(produced)}"
    limit = min(len(produced), len(expected))
    for i in range(limit):
        if produced[i] != expected[i]:
            lo = max(0, i - context)
            return (
                f"first mismatch at offset {i} ({note})\n"
                f"produced: {produced[lo : i + context]!r}\n"
                f"expected: {expected[lo : i + context]!r}"
            )
    return f"no byte mismatch in common prefix but {note}"
