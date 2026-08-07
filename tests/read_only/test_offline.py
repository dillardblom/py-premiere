"""ProjectItem.is_offline against the `16_offline` fixture."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_offline_item() -> None:
    # The bmp was set offline via UXP createSetOfflineAction
    # (Media/OfflineReason = 5).
    application = py_premiere.parse(MINIMAL / "16_offline.prproj")
    bmp = next(
        c for c in application.project.root_item.children if c.name == "red_64x36.bmp"
    )
    assert bmp.is_offline is True


def test_online_items_default_false() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    for child in application.project.root_item.children:
        assert child.is_offline is False


def test_bins_are_not_offline() -> None:
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")
    assert application.project.root_item.children[0].is_offline is False
