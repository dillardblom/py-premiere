"""ProjectItem color labels against the `11_labels` fixture."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _labels(prproj: str) -> dict[str, int]:
    application = py_premiere.parse(MINIMAL / prproj)

    def walk(item: py_premiere.models.ProjectItem):
        yield item
        for child in item.children:
            yield from walk(child)

    return {item.name: item.color_label for item in walk(application.project.root_item)}


def test_applied_labels() -> None:
    # UXP applied FOREST/ROSE/MANGO/PURPLE (5/6/7/8) in item order.
    labels = _labels("11_labels.prproj")
    assert labels["red_64x36.bmp"] == 5
    assert labels["renamed tone"] == 6
    assert labels["Seq A"] == 7
    assert labels["Seq B"] == 8


def test_root_defaults_to_zero() -> None:
    labels = _labels("11_labels.prproj")
    assert labels["11_labels.prproj"] == 0


def test_default_labels_present() -> None:
    # Premiere assigns a per-media-type default even without user action.
    labels = _labels("06_api.prproj")
    assert labels["red_64x36.bmp"] == 3
    assert labels["renamed tone"] == 2
