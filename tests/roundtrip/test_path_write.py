"""The shape-path writer and the drawn-mask subpath decode."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models.component import (
    PathVertex,
    _decode_subpaths,
    _encode_subpaths,
)

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _drawn_mask(
    application: py_premiere.models.Application,
) -> py_premiere.models.Component:
    clip = next(
        c
        for s in application.project.sequences
        for c in s.clips
        if any(comp.sub_components for comp in c.components)
    )
    return next(c for c in clip.components if c.sub_components).sub_components[0]


def test_drawn_ellipse_decodes_to_real_vertices() -> None:
    # The old reader silently mis-parsed the subpath layout into one
    # denormal-garbage vertex; the drawn ellipse is four anchors centred
    # exactly on the mask's Position (0.503, 0.458).
    mask = _drawn_mask(py_premiere.parse(MINIMAL / "26_effect_mask.prproj"))
    path = mask["Path"].path
    assert path is not None and len(path) == 4
    assert [round(v.x, 3) for v in path] == [0.503, 0.866, 0.503, 0.140]
    assert [round(v.y, 3) for v in path] == [0.183, 0.458, 0.734, 0.458]
    assert all(v.flag == 1.0 for v in path)


def test_encode_decode_is_byte_identical_on_the_fixture() -> None:
    mask = _drawn_mask(py_premiere.parse(MINIMAL / "26_effect_mask.prproj"))
    raw = mask["Path"]._payload()
    subpaths, closed = _decode_subpaths(raw, 1)
    assert _encode_subpaths(subpaths, bool(closed)) == raw


def test_rewriting_the_fixtures_own_vertices_reproduces_the_payload() -> None:
    mask = _drawn_mask(py_premiere.parse(MINIMAL / "26_effect_mask.prproj"))
    param = mask["Path"]
    original = param._payload()
    param.path = param.path
    assert param._payload() == original


def test_set_path_round_trips(tmp_path) -> None:
    # Draw a triangle on the clip-level mask (empty by default) and read
    # it back from the saved file.
    application = py_premiere.parse(MINIMAL / "26_effect_mask.prproj")
    clip = next(
        c
        for s in application.project.sequences
        for c in s.clips
        if c.selection_components
    )
    triangle = [
        PathVertex(0.5, 0.1, 0.5, 0.1, 0.5, 0.1, 1.0),
        PathVertex(0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 1.0),
        PathVertex(0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 1.0),
    ]
    clip.selection_components[0]["Path"].path = triangle
    target = tmp_path / "triangle.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    fresh_clip = next(
        c for s in fresh.project.sequences for c in s.clips if c.selection_components
    )
    read_back = fresh_clip.selection_components[0]["Path"].path
    assert read_back is not None
    assert [(round(v.x, 4), round(v.y, 4)) for v in read_back] == [
        (0.5, 0.1),
        (0.9, 0.9),
        (0.1, 0.9),
    ]
    fresh_clip.selection_components[0]["Path"].path = []
    assert fresh_clip.selection_components[0]["Path"].path == []


def test_set_path_validation() -> None:
    application = py_premiere.parse(MINIMAL / "26_effect_mask.prproj")
    mask = _drawn_mask(application)
    with pytest.raises(TypeError):
        mask["Path"].path = "not a list"
    with pytest.raises(TypeError):
        mask["Path"].path = [(0.5, 0.5)]
    with pytest.raises(ValueError, match="finite"):
        mask["Path"].path = [PathVertex(float("inf"), 0, 0, 0, 0, 0, 1.0)]
    with pytest.raises(ValueError, match="Path parameter"):
        mask["Feather"].path = []
