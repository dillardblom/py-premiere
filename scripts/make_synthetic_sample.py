"""Regenerate `samples/models/synthetic_roundtrip.prproj`.

A py-written fixture - NOT a valid Premiere project - that exercises the
gzip framing and serializer paths (entities, blob block form, expanded empty
container, pairs) in CI, where the real, unredistributable samples are
absent. Run from the repo root:

    uv run python scripts/make_synthetic_sample.py
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from py_premiere.xml.document import PremiereDocument
from py_premiere.xml.gzip_io import GzipFraming

OUT = (
    Path(__file__).resolve().parent.parent
    / "samples"
    / "models"
    / "synthetic_roundtrip.prproj"
)


def build_root() -> ET.Element:
    root = ET.Element("PremiereData", {"Version": "3"})
    root.text = "\n\t"

    stub = ET.SubElement(root, "Project", {"ObjectRef": "1"})
    stub.tail = "\n\t"

    project = ET.SubElement(
        root, "Project", {"ObjectID": "1", "ClassID": "0-0-0-0", "Version": "38"}
    )
    project.text = "\n\t\t"
    project.tail = "\n\t"
    name = ET.SubElement(project, "Name")
    name.text = "synthetic & <fixture>\nsecond line"
    name.tail = "\n\t\t"
    empty = ET.SubElement(project, "Container")
    empty.text = "\n\t\t"
    empty.tail = "\n\t"

    sequence = ET.SubElement(
        root, "Sequence", {"ObjectUID": "00000000-0000-0000-0000-000000000001"}
    )
    sequence.text = "\n\t\t"
    sequence.tail = "\n"
    blob = ET.SubElement(sequence, "ModificationState")
    blob.text = "QUJDREVGRw==\n\t\t"
    blob.tail = "\n\t\t"
    owner = ET.SubElement(sequence, "Owner", {"ObjectRef": "1"})
    owner.tail = "\n\t"
    return root


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    document = PremiereDocument(build_root(), GzipFraming.default())
    data = document.to_bytes()
    # The fixture must satisfy the same contract as real samples.
    reparsed = PremiereDocument.from_bytes(data)
    assert reparsed.to_bytes() == data
    OUT.write_bytes(data)
    print(f"wrote {OUT} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
