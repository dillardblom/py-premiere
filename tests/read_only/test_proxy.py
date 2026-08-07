"""ProjectItem proxy accessors against the `18_proxy` fixture."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_proxied_item() -> None:
    # A 32x18 proxy attached to the 64x36 H.264 clip via ExtendScript
    # attachProxy: a second Media object (flagged IsProxy) hung off the media
    # source's Content bag as ProxyMedia.
    application = py_premiere.parse(MINIMAL / "18_proxy.prproj")
    clip = application.project.root_item.children[0]
    assert clip.has_proxy is True
    assert clip.proxy_path.name == "bars_32x18_proxy.mp4"
    # The item still reports its HI-RES media as the media path.
    assert clip.media_path.name == "bars_64x36_h264.mp4"


def test_items_without_a_proxy() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    for child in application.project.root_item.children:
        assert child.has_proxy is False
        assert child.proxy_path is None


def test_bins_have_no_proxy() -> None:
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")
    root = application.project.root_item
    assert root.has_proxy is False
    assert root.children[0].has_proxy is False
