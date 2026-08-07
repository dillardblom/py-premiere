"""`ProjectItem.attach_proxy` against Premiere's own attachProxy."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.xml.mutations import remove_child

MINIMAL = SAMPLES_DIR / "models" / "minimal"
ASSETS = SAMPLES_DIR / "models" / "assets"


def _leaves(element: ET.Element, base: str = "") -> dict[str, str]:
    out = {}
    for child in element:
        path = f"{base}/{child.tag}"
        if len(child):
            out.update(_leaves(child, path))
        else:
            out[path] = (child.text or "").strip()
    return out


def test_strip_and_reattach_matches_premieres_own_proxy(tmp_path) -> None:
    # Remove Premiere's own proxy wiring from 18_proxy, re-attach the same
    # file through py, and compare the synthesized Media + VideoStream
    # leaf-for-leaf with what Premiere wrote (fresh identity GUIDs aside).
    application = py_premiere.parse(MINIMAL / "18_proxy.prproj")
    document = application.project._document
    item = application.project.root_item.children[0]
    reference_media = item._proxy_media()
    reference_stream = document.resolve(reference_media.find("VideoStream"))
    expected_media = _leaves(reference_media)
    expected_stream = _leaves(reference_stream)

    content = item._media_content()
    remove_child(content, content.find("ProxyMedia"))
    document.remove_object(reference_media)
    document.remove_object(reference_stream)
    assert item.has_proxy is False

    item.attach_proxy(ASSETS / "bars_32x18_proxy.mp4")
    assert item.has_proxy is True
    created_media = item._proxy_media()
    created_stream = document.resolve(created_media.find("VideoStream"))

    actual_media = _leaves(created_media)
    actual_stream = _leaves(created_stream)
    # Fresh identity: content-state hashes are py-minted GUIDs (Premiere
    # refreshes them on open), and FileKey identifies the file per session.
    for volatile in ("/ModificationState", "/ContentAndMetadataState", "/FileKey"):
        expected_media.pop(volatile, None)
        actual_media.pop(volatile, None)
    assert actual_media == expected_media
    assert actual_stream == expected_stream

    target = tmp_path / "reattached.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_item = fresh.project.root_item.children[0]
    assert fresh_item.has_proxy is True
    assert fresh_item.proxy_path.name == "bars_32x18_proxy.mp4"


def test_attach_proxy_round_trips_on_a_proxyless_project(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    application.project.import_files([ASSETS / "bars_64x36_h264.mp4"])
    item = application.project.root_item.children["bars_64x36_h264.mp4"]
    assert item.has_proxy is False
    item.attach_proxy(ASSETS / "bars_32x18_proxy.mp4")
    target = tmp_path / "proxied.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_item = fresh.project.root_item.children["bars_64x36_h264.mp4"]
    assert fresh_item.has_proxy is True
    assert fresh_item.proxy_path.name == "bars_32x18_proxy.mp4"
    # The item still reports the hi-res media path.
    assert fresh_item.media_path.name == "bars_64x36_h264.mp4"


GENERATED = SAMPLES_DIR / "refs" / "gaps" / "proxy_hires.prproj"


def test_hi_res_attach_swaps_the_roles(tmp_path) -> None:
    # ExtendScript's `attachProxy(path, isHiRes=1)`: the file passed in
    # becomes what the item PLAYS, and what it played is demoted to the
    # proxy. Both directions land on the same graph.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    application.project.import_files([ASSETS / "bars_32x18_proxy.mp4"])
    item = application.project.root_item.children["bars_32x18_proxy.mp4"]
    assert item.media_path.name == "bars_32x18_proxy.mp4"

    item.attach_proxy(ASSETS / "bars_64x36_h264.mp4", is_hi_res=True)

    target = tmp_path / "hires.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    # The master takes the new file's name, as Premiere's own call does;
    # the panel item's own `Name` copy is left on the old file.
    fresh_item = fresh.project.root_item.children["bars_64x36_h264.mp4"]
    assert fresh_item._element.findtext("ProjectItem/Name") == "bars_32x18_proxy.mp4"
    assert fresh_item.has_proxy is True
    assert fresh_item.media_path.name == "bars_64x36_h264.mp4"
    assert fresh_item.proxy_path.name == "bars_32x18_proxy.mp4"


@pytest.mark.skipif(
    not GENERATED.exists(), reason="the hi-res proxy fixture is local-only"
)
def test_hi_res_attach_matches_premieres_own(tmp_path) -> None:
    # Against Premiere's own `attachProxy(64x36, 1)` on a 32x18 item.
    reference = py_premiere.parse(GENERATED)
    reference_item = reference.project.root_item.children[0]
    expected_proxy = _leaves(reference_item._proxy_media())
    expected_stream = _leaves(
        reference.project._document.resolve(
            reference_item._proxy_media().find("VideoStream")
        )
    )

    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    application.project.import_files([ASSETS / "bars_32x18_proxy.mp4"])
    item = application.project.root_item.children["bars_32x18_proxy.mp4"]
    item.attach_proxy(ASSETS / "bars_64x36_h264.mp4", is_hi_res=True)

    actual_proxy = _leaves(item._proxy_media())
    actual_stream = _leaves(
        application.project._document.resolve(item._proxy_media().find("VideoStream"))
    )
    # `RelativePath` is relative to each project's OWN location, and the
    # two projects live in different folders.
    for volatile in (
        "/ModificationState",
        "/ContentAndMetadataState",
        "/FileKey",
        "/RelativePath",
    ):
        expected_proxy.pop(volatile, None)
        actual_proxy.pop(volatile, None)
    assert actual_proxy == expected_proxy
    # Premiere additionally stamps field-type and ignore-alpha overrides on
    # the demoted stream; py writes only the frame-rect one, so compare the
    # fields both carry.
    shared = set(expected_stream) & set(actual_stream)
    assert {key: actual_stream[key] for key in shared} == {
        key: expected_stream[key] for key in shared
    }
    assert "/OverriddenFrameRect" in shared


def test_attach_proxy_validation() -> None:
    application = py_premiere.parse(MINIMAL / "18_proxy.prproj")
    item = application.project.root_item.children[0]
    with pytest.raises(ValueError, match="already has"):
        item.attach_proxy(ASSETS / "bars_32x18_proxy.mp4")

    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    application.project.import_files([ASSETS / "bars_64x36_h264.mp4"])
    clip = application.project.root_item.children["bars_64x36_h264.mp4"]
    with pytest.raises(ValueError, match="does not exist"):
        clip.attach_proxy(ASSETS / "does_not_exist.mp4")
    # Every committed movie asset is 16:9, so the aspect check is
    # exercised directly rather than through a mismatched file.
    with pytest.raises(ValueError, match="aspect ratio"):
        application.project._make_proxy_media(
            ASSETS / "bars_32x18_proxy.mp4", "0,0,64,48"
        )
