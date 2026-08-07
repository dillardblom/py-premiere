"""The keyframe and shape-path encodings decoded by the deep-RE pass."""

from __future__ import annotations

import base64
import json
import xml.etree.ElementTree as ET

from py_premiere.enums import KeyframeInterpolation
from py_premiere.models import Time
from py_premiere.models.component import ComponentParam
from py_premiere.xml import PremiereDocument

#: A real `Path` payload: the 540.04 x 260.1 rectangle mask stored in
#: `Abstract Slideshow`. Version 2, four vertices, seven floats each - a
#: leading flag, the point, and its two (coincident, i.e. corner) handles.
RECTANGLE = (
    "AgAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAF4CB0QAAAAAXgIHRAAAAABe"
    "AgdEAAAAAAAAAABeAgdEagyCQ14CB0RqDIJDXgIHRGoMgkMAAAAAAAAAAGoMgkMAAAAAagyCQwAA"
    "AABqDIJDAQ=="
)


def _param(children: dict[str, str]) -> ComponentParam:
    element = ET.Element("ArbVideoComponentParam")
    for tag, text in children.items():
        ET.SubElement(element, tag).text = text
    document = PremiereDocument(ET.Element("PremiereData"), None)
    return ComponentParam(element, document, None)  # type: ignore[arg-type]


def test_decodes_a_shape_path() -> None:
    path = _param({"Name": "Path", "StartKeyframeValue": RECTANGLE}).path
    assert path is not None
    assert [(round(v.x, 2), round(v.y, 2)) for v in path] == [
        (0.0, 0.0),
        (540.04, 0.0),
        (540.04, 260.1),
        (0.0, 260.1),
    ]
    # A corner point keeps both handles on the point itself.
    for vertex in path:
        assert (vertex.in_x, vertex.in_y) == (vertex.x, vertex.y)
        assert (vertex.out_x, vertex.out_y) == (vertex.x, vertex.y)


def test_empty_shape_path() -> None:
    # A rectangle or ellipse mask stores NO vertices - its geometry lives in
    # the sibling Type/Scale/Rotation params - so an empty list is a real
    # answer, distinct from "this parameter holds no shape at all".
    assert _param({"Name": "Path", "StartKeyframeValue": "AgAAAAAAAAA="}).path == []
    assert _param({"Name": "Opacity"}).path is None


def test_rejects_a_foreign_payload() -> None:
    # Other arbitrary-data params (Tracker, Appearance) start with a
    # different version word and must not be read as shapes.
    assert (
        _param({"Name": "Tracker", "StartKeyframeValue": "AQAAAAAAgD8="}).path is None
    )


def test_incoming_and_outgoing_interpolation() -> None:
    # Field 3 is the OUTGOING interpolation: across the corpus it is
    # non-zero only where the incoming one is BEZIER.
    param = _param(
        {
            "Keyframes": "100,50.,5,4,0,0,0,0;200,60.,0,0,0,0,0,0;",
        }
    )
    assert param.get_interpolation_at_key(Time(100)) is KeyframeInterpolation.BEZIER
    assert param.get_out_interpolation_at_key(Time(100)) is KeyframeInterpolation.HOLD
    # The common case: a key leaves the way it arrived.
    assert param.get_interpolation_at_key(Time(200)) is KeyframeInterpolation.LINEAR
    assert param.get_out_interpolation_at_key(Time(200)) is KeyframeInterpolation.LINEAR
    assert param.get_out_interpolation_at_key(Time(999)) is None


def test_spatial_tangents_of_a_point_keyframe() -> None:
    # A 2D keyframe's last four fields are the motion-path handles, which
    # sit after a constant pair and are distinct from the temporal slopes
    # earlier in the entry.
    param = _param(
        {
            "Keyframes": (
                "100,0.5:0.5,0,0,1,0.16,2,0.33,5,4,0,0,0.048,0;"
                "200,0.6:0.5,0,0,1,0.16,2,0.33,5,4,-0.048,-0,0,0;"
            )
        }
    )
    first = param.get_spatial_tangents_at_key(Time(100))
    assert first == (0.0, 0.0, 0.048, 0.0)
    # Adjacent keys mirror each other across the segment between them.
    assert param.get_spatial_tangents_at_key(Time(200)) == (-0.048, -0.0, 0.0, 0.0)
    assert param.get_spatial_tangents_at_key(Time(999)) is None


def test_scalar_keyframes_have_no_motion_path() -> None:
    scalar = _param({"Keyframes": "100,50.,0,0,0,0,0,0;"})
    assert scalar.get_spatial_tangents_at_key(Time(100)) is None


def test_decodes_template_parameter_text() -> None:
    # A Motion Graphics template's text control stores UTF-16LE JSON; the
    # edited text is under `textEditValue`. Payload from the `Credit Text 01`
    # mogrt (the template itself is not redistributable, so only the
    # encoding is checked here).
    encoded = base64.b64encode(
        '{"textEditValue":"Rachel Green"}'.encode("utf-16-le")
    ).decode()
    text = _param({"Name": "Part 01 Text 01", "StartKeyframeValue": encoded}).text
    assert text is not None
    assert json.loads(text)["textEditValue"] == "Rachel Green"


def test_binary_payloads_are_not_text() -> None:
    # The shape blob behind `path` is binary: reading it as text must not
    # produce mojibake.
    assert _param({"Name": "Path", "StartKeyframeValue": RECTANGLE}).text is None
    assert _param({"Name": "Opacity"}).text is None


def test_text_resolves_through_the_payload_hash() -> None:
    # Premiere stores a payload once and writes every further copy as an
    # empty element with the same BinaryHash, so a template clip's own
    # parameters are usually empty.
    encoded = base64.b64encode("shared".encode("utf-16-le")).decode()
    root = ET.Element("PremiereData")
    populated = ET.SubElement(ET.SubElement(root, "Original"), "StartKeyframeValue")
    populated.set("BinaryHash", "hash-1")
    populated.text = encoded
    document = PremiereDocument(root, None)
    empty = ET.Element("ArbVideoComponentParam")
    ET.SubElement(empty, "StartKeyframeValue").set("BinaryHash", "hash-1")
    assert ComponentParam(empty, document, None).text == "shared"  # type: ignore[arg-type]
