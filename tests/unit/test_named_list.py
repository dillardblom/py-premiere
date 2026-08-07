"""Unit tests for the `NamedList` collection view."""

from __future__ import annotations

import pytest

from py_premiere.models import NamedList


class _Item:
    def __init__(self, name: str) -> None:
        self.name = name


class _Effect:
    def __init__(self, display_name: str, match_name: str) -> None:
        self.display_name = display_name
        self.match_name = match_name


def test_list_behaviour_is_preserved() -> None:
    a, b = _Item("a"), _Item("b")
    items = NamedList([a, b])
    assert items[0] is a
    assert items[-1] is b
    assert items[0:1] == [a]
    assert len(items) == 2
    assert list(items) == [a, b]
    assert a in items


def test_lookup_by_name() -> None:
    a, b, b2 = _Item("a"), _Item("b"), _Item("b")
    items = NamedList([a, b, b2])
    assert items["a"] is a
    # The FIRST match wins, like every find-by-name API.
    assert items["b"] is b
    assert "a" in items
    assert "missing" not in items
    with pytest.raises(KeyError):
        items["missing"]


def test_get_with_default() -> None:
    a = _Item("a")
    items = NamedList([a])
    assert items.get("a") is a
    assert items.get("missing") is None
    fallback = _Item("fallback")
    assert items.get("missing", fallback) is fallback


def test_alternate_keys() -> None:
    blur = _Effect("Gaussian Blur", "AE.ADBE Gaussian Blur 2")
    effects = NamedList([blur], keys=("display_name", "match_name"))
    assert effects["Gaussian Blur"] is blur
    assert effects["AE.ADBE Gaussian Blur 2"] is blur
    assert "AE.ADBE Gaussian Blur 2" in effects


def test_view_is_a_snapshot() -> None:
    backing = [_Item("a")]
    items = NamedList(backing)
    items.append(_Item("b"))
    assert len(backing) == 1
