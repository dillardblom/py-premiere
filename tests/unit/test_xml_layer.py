"""Unit tests for the xml layer (no sample projects)."""

from __future__ import annotations

import gzip
import io
import xml.etree.ElementTree as ET

import pytest

from py_premiere.xml import PremiereDocument
from py_premiere.xml.serializer import serialize_document

PAYLOAD = (
    b'<?xml version="1.0" encoding="UTF-8" ?>\n'
    b'<PremiereData Version="3">\n'
    b'\t<Project ObjectRef="1"/>\n'
    b'\t<Project ObjectID="1" ClassID="guid" Version="38">\n'
    b"\t\t<Name>a&#10;b&#13;c &amp; d &gt; e</Name>\n"
    b"\t</Project>\n"
    b'\t<Sequence ObjectUID="uid-1">\n'
    b'\t\t<Target ObjectURef="uid-1"/>\n'
    b"\t</Sequence>\n"
    b"</PremiereData>\n\n"
)


def test_payload_round_trips() -> None:
    document = PremiereDocument.from_bytes(PAYLOAD)
    assert document.framing is None
    assert document.to_bytes() == PAYLOAD


def test_entities_decoded() -> None:
    document = PremiereDocument.from_bytes(PAYLOAD)
    name = document.by_object_id["1"].find("Name")
    assert name is not None
    assert name.text == "a\nb\rc & d > e"


def test_mutated_leaf_reescapes() -> None:
    document = PremiereDocument.from_bytes(PAYLOAD)
    name = document.by_object_id["1"].find("Name")
    assert name is not None
    name.text = "x<y&z\nnew"
    assert b"<Name>x&lt;y&amp;z&#10;new</Name>" in document.to_bytes()


def test_resolve_by_uid() -> None:
    document = PremiereDocument.from_bytes(PAYLOAD)
    target = document.root.find("Sequence/Target")
    assert target is not None
    assert document.resolve(target).get("ObjectUID") == "uid-1"


def test_resolve_without_ref_raises() -> None:
    document = PremiereDocument.from_bytes(PAYLOAD)
    with pytest.raises(ValueError, match="no ObjectRef/ObjectURef"):
        document.resolve(document.root)


def test_resolve_unknown_id_raises_value_error() -> None:
    document = PremiereDocument.from_bytes(PAYLOAD)
    dangling = ET.Element("X", {"ObjectRef": "999"})
    with pytest.raises(ValueError, match="unknown ObjectID '999'"):
        document.resolve(dangling)


def test_resolve_refuses_scoped_subtree_refs() -> None:
    payload = (
        b'<?xml version="1.0" encoding="UTF-8" ?>\n'
        b"<PremiereData>\n"
        b'\t<Project ObjectID="1">\n'
        b'\t\t<ViewState ObjectID="2">\n'
        b'\t\t\t<Second ObjectRef="1"/>\n'
        b"\t\t</ViewState>\n"
        b"\t</Project>\n"
        b"</PremiereData>\n\n"
    )
    document = PremiereDocument.from_bytes(payload)
    scoped_ref = document.root.find("Project/ViewState/Second")
    assert scoped_ref is not None
    with pytest.raises(ValueError, match="scoped inline-definition"):
        document.resolve(scoped_ref)


def test_expanded_empty_container_round_trips() -> None:
    payload = b'<?xml version="1.0" encoding="UTF-8" ?>\n<A>\n\t<B>\n\t</B>\n</A>\n\n'
    document = PremiereDocument.from_bytes(payload)
    assert document.to_bytes() == payload


def test_blob_leaf_block_form_round_trips() -> None:
    payload = b'<?xml version="1.0" encoding="UTF-8" ?>\n<A>\n\t<Blob>QUJD++==\n\t</Blob>\n</A>\n\n'
    document = PremiereDocument.from_bytes(payload)
    blob = document.root.find("Blob")
    assert blob is not None
    assert blob.text == "QUJD++==\n\t"
    assert document.to_bytes() == payload


def test_leaf_data_ending_with_newline_stays_entity() -> None:
    payload = (
        b'<?xml version="1.0" encoding="UTF-8" ?>\n<A>\n\t<W>data&#10;</W>\n</A>\n\n'
    )
    document = PremiereDocument.from_bytes(payload)
    w = document.root.find("W")
    assert w is not None
    assert w.text == "data\n"
    assert document.to_bytes() == payload


def test_empty_element_self_closes() -> None:
    root = ET.Element("A", {"K": "v"})
    ET.SubElement(root, "B")
    expected = b'<?xml version="1.0" encoding="UTF-8" ?>\n<A K="v"><B/></A>\n\n'
    assert serialize_document(root) == expected


def test_attribute_escaping() -> None:
    root = ET.Element("A", {"K": 'a"b<c&d\ne\tf'})
    serialized = serialize_document(root)
    assert b'K="a&quot;b&lt;c&amp;d&#10;e&#9;f"' in serialized


def test_mixed_content_rejected() -> None:
    with pytest.raises(ValueError, match="mixed content"):
        PremiereDocument.from_bytes(b"<A>text<B/></A>")
    with pytest.raises(ValueError, match="mixed content"):
        PremiereDocument.from_bytes(b"<A><B/>trailing</A>")


def test_mutated_branch_text_refused_at_serialize() -> None:
    document = PremiereDocument.from_bytes(PAYLOAD)
    sequence = document.by_object_uid["uid-1"]
    sequence.text = "not formatting"
    with pytest.raises(ValueError, match="mixed content"):
        document.to_bytes()


def test_duplicate_object_id_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate ObjectID"):
        PremiereDocument.from_bytes(b'<A><B ObjectID="1"/><C ObjectID="1"/></A>')


def test_unrepresentable_constructs_rejected() -> None:
    # ElementTree normalizes these away; the self-check must refuse rather
    # than silently rewrite on save.
    cases = [
        b"<A>\n\t<!-- a comment -->\n\t<B/>\n</A>\n\n",  # comment dropped
        b"<A>\n\t<B></B>\n</A>\n\n",  # expanded empty pair -> would self-close
        b"<A>\n\t<W>&#10;</W>\n</A>\n\n",  # whitespace-only entity leaf
        b'<?xml version="1.0" encoding="UTF-8"?>\n<A/>\n\n',  # prolog variant
    ]
    for payload in cases:
        with pytest.raises(ValueError, match="round-trip"):
            PremiereDocument.from_bytes(payload)


def test_fname_gzip_header_preserved() -> None:
    # A .prproj re-gzipped by CLI tools carries FNAME; header must be parsed
    # and re-emitted verbatim (compresslevel 6 matches our writer).
    buffer = io.BytesIO()
    with gzip.GzipFile(
        filename="inner.xml", mode="wb", fileobj=buffer, compresslevel=6, mtime=0
    ) as member:
        member.write(PAYLOAD)
    data = buffer.getvalue()
    document = PremiereDocument.from_bytes(data)
    assert document.framing is not None
    assert b"inner.xml" in document.framing.header
    assert document.to_bytes() == data


def test_truncated_gzip_rejected() -> None:
    with pytest.raises(ValueError, match="truncated gzip"):
        PremiereDocument.from_bytes(b"\x1f\x8b\x08")


def test_multi_member_gzip_rejected() -> None:
    data = gzip.compress(b"<A/>", 6) + gzip.compress(b"<B/>", 6)
    with pytest.raises(ValueError, match="multi-member"):
        PremiereDocument.from_bytes(data)


def test_from_bytes_reports_a_non_project_file_as_a_value_error() -> None:
    with pytest.raises(ValueError, match="not a Premiere project file"):
        PremiereDocument.from_bytes(gzip.compress(b"not xml at all"))
    with pytest.raises(ValueError, match="not a Premiere project file"):
        PremiereDocument.from_bytes(b"")
