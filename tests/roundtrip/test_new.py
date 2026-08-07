"""py_premiere.new(): the from-scratch empty project.

`new()` builds the project rather than replaying a captured one. Premiere
restores everything it leaves out - the compile-settings tree and the 26.7 KB
of panel view state - on first save; the evidence is
`samples/refs/skeleton/py_new_resave.prproj`, Premiere's own resave of a
project this code produced, which comes back as the full 40 objects.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.models.skeleton import build_empty_project
from py_premiere.xml.serializer import serialize_document

GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _xml(application: py_premiere.Application) -> str:
    return application.project._document.to_xml_bytes().decode("utf-8")


def test_new_is_empty() -> None:
    application = py_premiere.new()
    assert application.project.root_item.children == []
    assert application.project.sequences == []
    assert application.project.name == "untitled.prproj"
    # The root bin is stored as "Root Bin" but reports the project name, as
    # Premiere's own panel does.
    assert application.project.root_item.name == "untitled.prproj"


def test_each_project_gets_its_own_identifiers() -> None:
    # The bundled skeleton gave every project the SAME documentID, because it
    # was one captured file replayed.
    first, second = py_premiere.new().project, py_premiere.new().project
    assert first.document_id != second.document_id
    assert GUID.fullmatch(first.document_id)
    for name in ("MZ.Project.GUID", "ProjectViewState.ID"):
        values = []
        for application in (py_premiere.new(), py_premiere.new()):
            found = re.search(f"<{name}>([^<]*)</{name}>", _xml(application))
            assert found is not None, name
            values.append(found.group(1))
        assert values[0] != values[1], name


def test_no_machine_specific_state() -> None:
    # The captured skeleton embedded the capturing machine's home directory
    # and its GPU renderer choice in every project py ever created.
    xml = _xml(py_premiere.new())
    assert "lastknowngoodprojectpath" not in xml
    assert "lastknownparentdirectorypathaboveprojectpath" not in xml
    assert "AcceleratedRenderer" not in xml


def test_round_trips_byte_for_byte(tmp_path) -> None:
    application = py_premiere.new()
    target = tmp_path / "empty.prproj"
    application.project.save(target)
    original = target.read_bytes()
    again = tmp_path / "again.prproj"
    py_premiere.parse(target).project.save(again)
    assert again.read_bytes() == original


def test_matches_premieres_own_skeleton_element_for_element() -> None:
    # Against the same project with everything Premiere regenerates stripped
    # out: identical but for the three identifiers and the machine-state keys
    # that are deliberately gone.
    stripped = SAMPLES_DIR / "refs" / "skeleton" / "minimal.prproj"
    if not stripped.exists():
        pytest.skip("local-only reference (scripts/dev/strip_empty_project.py)")
    theirs = ET.fromstring(py_premiere.parse(stripped).project._document.to_xml_bytes())
    mine = ET.fromstring(
        serialize_document(
            build_empty_project(
                document_id="b23dc5a3-5db5-4b4a-ad56-e98dccf9c2a6",
                project_guid="f944c518-3ea1-48bc-89a4-72958ee8d595",
                view_state_id="6361763e-4734-4d86-83f7-83d3eb153344",
            )
        )
    )
    assert [child.tag for child in theirs] == [child.tag for child in mine]
    dropped = {
        "BE.Prefs.AcceleratedRenderer.LastUsedIdentifier",
        "BE.Prefs.AcceleratedRenderer.LastUsedDisplayName",
    }

    def leaves(root: ET.Element) -> list[tuple[str, str]]:
        return [
            (element.tag, (element.text or "").strip())
            for element in root.iter()
            if not list(element)
            and element.tag not in dropped
            and not element.tag.startswith("list.view.")
        ]

    assert leaves(mine) == leaves(theirs)


def test_new_project_is_editable(tmp_path) -> None:
    application = py_premiere.new()
    application.project.root_item.add_bin("Footage")
    target = tmp_path / "edited.prproj"
    application.project.save(target)
    fresh = py_premiere.parse(target)
    assert [c.name for c in fresh.project.root_item.children] == ["Footage"]


def test_premiere_restores_what_the_skeleton_omits() -> None:
    # The recorded verdict: Premiere opened a project this builder wrote and
    # saved it back as the full 40-object form.
    resave = SAMPLES_DIR / "refs" / "skeleton" / "py_new_resave.prproj"
    if not resave.exists():
        pytest.skip("local-only reference (Premiere resave of a py-built project)")
    xml = py_premiere.parse(resave).project._document.to_xml_bytes().decode("utf-8")
    assert len(re.findall(r"\n\t<\w+", xml)) == 40
    assert "ProjectViewState.List" in xml
    assert xml.count("CompileSettings ObjectRef") == 17
