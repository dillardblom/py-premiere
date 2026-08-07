"""SRT import against Premiere's own import in 29_captions."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.xml.document import ReferenceIndex

MINIMAL = SAMPLES_DIR / "models" / "minimal"
SRT = SAMPLES_DIR / "models" / "assets" / "two_lines.srt"


def _leaves(element: ET.Element, base: str = "") -> dict[str, str]:
    out = {}
    for child in element:
        path = f"{base}/{child.tag}"
        if len(child):
            out.update(_leaves(child, path))
        else:
            out[path] = (child.text or "").strip()
    return out


def _graph(
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


#: Fresh per-import identity and view state; everything else - the cue map,
#: times, payload text bytes included - must match Premiere's own import.
_VOLATILE = (
    "/DataClip/Clip/ClipID",
    "/MasterClipChangeVersion",
    "/ModificationState",
    "/FileKey",
    "/ContentAndMetadataState",
    "/LastContentState",
    "/ProjectItem/Node/Properties/project.icon.view.grid.order",
)


def test_import_matches_premieres_own() -> None:
    reference = _graph(
        py_premiere.parse(MINIMAL / "29_captions.prproj"), "two_lines.srt"
    )
    # 06_api lives in the same directory as 29_captions, so even the
    # stored RelativePath must come out identical.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    application.project.import_files([SRT])
    mine = _graph(application, "two_lines.srt")

    assert sorted(mine) == sorted(reference)
    for tag, elements in mine.items():
        assert len(elements) == len(reference[tag]), f"{tag} count differs"
        for element, expected_element in zip(elements, reference[tag]):
            expected = _leaves(expected_element)
            actual = _leaves(element)
            for path in _VOLATILE:
                expected.pop(path, None)
                actual.pop(path, None)
            assert actual == expected, f"{tag} diverges from Premiere's import"


def test_srt_import_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    item = application.project.import_files([SRT])[0]
    assert item.name == "two_lines.srt"
    target = tmp_path / "srt.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    fresh_item = fresh.project.root_item.children["two_lines.srt"]
    assert fresh_item.media_path.name == "two_lines.srt"
    # The stream spans the last cue (2 s at the 30 fps caption rate).
    assert fresh_item.out_point.ticks == 508032000000
