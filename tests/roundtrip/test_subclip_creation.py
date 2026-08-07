"""`ProjectItem.create_sub_clip` against Premiere's own createSubClip."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Time
from py_premiere.xml.document import ReferenceIndex

MINIMAL = SAMPLES_DIR / "models" / "minimal"

#: The exact boundaries 28_subclip's ES createSubClip used.
_START = Time(63504000000)
_END = Time(190512000000)


def _leaves(element: ET.Element, base: str = "") -> dict[str, str]:
    out = {}
    for child in element:
        path = f"{base}/{child.tag}"
        if len(child):
            out.update(_leaves(child, path))
        else:
            out[path] = (child.text or "").strip()
    return out


def _owned_graph(
    application: py_premiere.models.Application, name: str
) -> dict[str, list[ET.Element]]:
    document = application.project._document
    item = application.project.root_item.children[name]
    index = ReferenceIndex(document)
    owned = document.owned_objects([item._element, item._master_element], index)
    graph: dict[str, list[ET.Element]] = {}
    for element in owned:
        graph.setdefault(element.tag, []).append(element)
    return graph


#: Leaf paths that legitimately differ from Premiere's own subclip: fresh
#: per-clip GUIDs, the change counter Premiere bumps per analysis pass, the
#: icon-view ordering key - view state py elides by policy (Premiere
#: regenerates it on open, as with the bin-creation view state) - and the
#: panel label stamp, which Premiere itself writes inconsistently
#: (28_subclip's subclip has none, 71_av_subclip's does; a resave
#: re-stamps it either way).
_VOLATILE = (
    "/Clip/ClipID",
    "/MasterClipChangeVersion",
    "/ProjectItem/Node/Properties/project.icon.view.grid.order",
    "/ProjectItem/Node/Properties/Column.PropertyText.Label",
)


def _graph_of(
    application: py_premiere.models.Application,
    item: py_premiere.models.ProjectItem,
) -> dict[str, list[ET.Element]]:
    document = application.project._document
    index = ReferenceIndex(document)
    owned = document.owned_objects([item._element, item._master_element], index)
    graph: dict[str, list[ET.Element]] = {}
    for element in owned:
        graph.setdefault(element.tag, []).append(element)
    return graph


def _assert_graphs_match(
    mine: dict[str, list[ET.Element]],
    reference: dict[str, list[ET.Element]],
    extra_volatile: tuple[str, ...] = (),
) -> None:
    assert sorted(mine) == sorted(reference)
    for tag, elements in mine.items():
        assert len(elements) == len(reference[tag]), f"{tag} count differs"
        for element, expected_element in zip(elements, reference[tag]):
            expected = _leaves(expected_element)
            actual = _leaves(element)
            for path in _VOLATILE + extra_volatile:
                expected.pop(path, None)
                actual.pop(path, None)
            if actual.get("/ProjectItem/Node/Properties") == "":
                # py's bag is empty where Premiere's holds only the elided
                # view-state key, which makes the container itself a leaf.
                actual.pop("/ProjectItem/Node/Properties")
            assert actual == expected, f"{tag} diverges from Premiere's subclip"


def test_create_matches_premieres_own_subclip() -> None:
    # 28_subclip holds Premiere's own subclip; py creates a second one from
    # the same source with the same arguments, and every leaf of the two
    # object graphs must agree (fresh GUIDs and the change counter aside).
    application = py_premiere.parse(MINIMAL / "28_subclip.prproj")
    source = application.project.root_item.children["bars_64x36_h264.mp4"]
    created = source.create_sub_clip("h264 subclip", _START, _END)

    reference = _owned_graph(application, "h264 subclip")
    mine = _graph_of(application, created)
    _assert_graphs_match(mine, reference)
    # The file identity is shared, and the modification blob is not
    # duplicated: the new Media hash-references the existing payload.
    state = mine["Media"][0].find("ModificationState")
    reference_state = reference["Media"][0].find("ModificationState")
    assert state.get("BinaryHash") == reference_state.get("BinaryHash")
    assert not (state.text or "").strip()


def test_av_subclip_matches_premieres_own() -> None:
    # 71_av_subclip holds Premiere's own A/V subclip: the identical
    # boundary trio lands on BOTH the video and the audio source. Extra
    # volatile leaves: the conform/peak cache paths (machine-local,
    # deliberately elided by py, re-stamped by Premiere on open) and the
    # per-master DefMappingID GUID.
    application = py_premiere.parse(MINIMAL / "71_av_subclip.prproj")
    source = application.project.root_item.children["bars_64x36_av.mp4"]
    created = source.create_sub_clip("av subclip", _START, _END)
    reference = _owned_graph(application, "av subclip")
    mine = _graph_of(application, created)
    _assert_graphs_match(
        mine,
        reference,
        extra_volatile=("/ConformedAudioPath", "/PeakFilePath", "/DefMappingID"),
    )
    assert created.is_subclip
    assert created.subclip_in_point == _START
    assert created.subclip_out_point == _END


def test_create_sub_clip_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "28_subclip.prproj")
    source = application.project.root_item.children["bars_64x36_h264.mp4"]
    source.create_sub_clip("py subclip", _START, _END, has_hard_boundaries=True)
    target = tmp_path / "subclip.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    item = fresh.project.root_item.children["py subclip"]
    assert item.is_subclip
    assert item.subclip_in_point == _START
    assert item.subclip_out_point == _END
    assert item.has_hard_boundaries is True
    assert item.media_path == source.media_path
    # The subclip's own in/out still span the whole file, like Premiere's.
    assert (
        item.out_point
        == fresh.project.root_item.children["bars_64x36_h264.mp4"].out_point
    )


def test_create_and_remove_restores_the_object_count() -> None:
    application = py_premiere.parse(MINIMAL / "28_subclip.prproj")
    document = application.project._document
    before = len(list(document.root))
    root = application.project.root_item
    created = root.children["bars_64x36_h264.mp4"].create_sub_clip("temp", _START, _END)
    root.remove_item(created)
    assert len(list(document.root)) == before


def test_boundary_validation() -> None:
    application = py_premiere.parse(MINIMAL / "28_subclip.prproj")
    source = application.project.root_item.children["bars_64x36_h264.mp4"]
    with pytest.raises(ValueError, match="0 <= start < end"):
        source.create_sub_clip("bad", _END, _START)
    with pytest.raises(ValueError, match="0 <= start < end"):
        source.create_sub_clip("bad", Time(-1), _END)
    root = application.project.root_item
    with pytest.raises(ValueError, match="clip items"):
        root.create_sub_clip("bad", _START, _END)


def test_av_subclip_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    application.project.import_files(
        [SAMPLES_DIR / "models" / "assets" / "bars_64x36_av.mp4"]
    )
    item = application.project.root_item.children["bars_64x36_av.mp4"]
    item.create_sub_clip("av sub", _START, _END, has_hard_boundaries=True)
    target = tmp_path / "av_subclip.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    sub = fresh.project.root_item.children["av sub"]
    assert sub.is_subclip
    assert sub.subclip_in_point == _START
    assert sub.has_hard_boundaries is True
