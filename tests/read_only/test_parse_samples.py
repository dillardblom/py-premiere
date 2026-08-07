"""Parse-level sanity over every local sample (no mutation)."""

from __future__ import annotations

from pathlib import Path

from helpers import each_sample

from py_premiere.xml import parse_prproj


@each_sample
def test_document_shape(path: Path) -> None:
    document = parse_prproj(path)
    assert document.root.tag == "PremiereData"
    assert document.by_object_id
    assert document.by_object_uid
    project_ref = document.root.find("Project")
    assert project_ref is not None
    project = document.resolve(project_ref)
    assert project.tag == "Project"
    assert project.get("ObjectID") == project_ref.get("ObjectRef")
