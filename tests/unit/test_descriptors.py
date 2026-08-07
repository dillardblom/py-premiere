"""Unit tests for XmlField and formatting-preserving insertion."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from py_premiere.models.descriptors import XmlField
from py_premiere.xml.mutations import insert_leaf_before
from py_premiere.xml.serializer import serialize_element


class _Holder:
    value = XmlField[str]("Inner/Value")
    absent = XmlField[str]("Inner/Absent")
    with_default = XmlField[str]("Inner/Absent", default="fallback")
    creatable = XmlField[str]("Inner/Absent", default="0", insert_before="Value")

    def __init__(self, element: ET.Element) -> None:
        self._element = element


def _holder() -> _Holder:
    element = ET.fromstring(
        "<Outer>\n\t<Inner>\n\t\t<Value>v</Value>\n\t</Inner>\n</Outer>"
    )
    return _Holder(element)


def test_get_and_set_existing() -> None:
    holder = _holder()
    assert holder.value == "v"
    holder.value = "w"
    assert holder.value == "w"


def test_missing_without_default_raises() -> None:
    with pytest.raises(ValueError, match="missing <Inner/Absent>"):
        _ = _holder().absent


def test_missing_with_default() -> None:
    assert _holder().with_default == "fallback"


def test_set_missing_without_anchor_raises() -> None:
    holder = _holder()
    with pytest.raises(ValueError, match="creation anchor"):
        holder.absent = "x"


def test_set_missing_creates_with_preserved_formatting() -> None:
    holder = _holder()
    holder.creatable = "5"
    assert holder.creatable == "5"
    inner = holder._element.find("Inner")
    assert inner is not None
    assert (
        serialize_element(inner)
        == b"<Inner>\n\t\t<Absent>5</Absent>\n\t\t<Value>v</Value>\n\t</Inner>"
    )


def test_insert_leaf_before_missing_anchor_raises() -> None:
    parent = ET.fromstring("<A><B/></A>")
    with pytest.raises(ValueError, match="no <X> child"):
        insert_leaf_before(parent, "X", "New", "1")
