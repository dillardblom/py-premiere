"""Sequence in/out/zero-point writes, including bag-key creation."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Time
from py_premiere.xml.mutations import remove_child

MINIMAL = SAMPLES_DIR / "models" / "minimal"

_TRIO = ("MZ.InPoint", "MZ.OutPoint", "MZ.ZeroPoint")


def test_strip_and_reset_trio_is_byte_identical(tmp_path) -> None:
    # 06_api stores all three; removing them and re-setting through the
    # setters (scrambled order) must reproduce Premiere's exact bytes.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    sequence = application.project.sequences[0]
    properties = sequence._element.find("Node/Properties")
    original = {key: sequence._bag_int(key) for key in _TRIO}
    for key in _TRIO:
        remove_child(properties, properties.find(key))
    sequence.zero_point = Time(original["MZ.ZeroPoint"])
    sequence.in_point = Time(original["MZ.InPoint"])
    sequence.out_point = Time(original["MZ.OutPoint"])
    target = tmp_path / "readd.prproj"
    application.project.save(target)
    assert target.read_bytes() == (MINIMAL / "06_api.prproj").read_bytes()


def test_points_read_none_when_unset_and_clear_to_none() -> None:
    # A freshly built sequence stores no in/out; py reports None where
    # ExtendScript reports the -400000 s sentinel. Clearing writes the
    # sentinel, which reads back as None.
    sequence = py_premiere.new().project.add_sequence("QoL")
    assert sequence.in_point is None
    assert sequence.out_point is None
    sequence.in_point = Time(254016000000)
    assert sequence.in_point == Time(254016000000)
    sequence.in_point = None
    assert sequence.in_point is None
    assert sequence._bag_int("MZ.InPoint") == -101606400000000000


def test_set_points_on_virgin_sequence_round_trips(tmp_path) -> None:
    # 04_sequence stores none of the trio; setting creates the keys.
    application = py_premiere.parse(MINIMAL / "04_sequence.prproj")
    sequence = application.project.sequences[0]
    assert sequence._bag_element("MZ.InPoint") is None
    sequence.in_point = Time(254016000000)
    sequence.out_point = Time(508032000000)
    sequence.zero_point = Time(254016000000)
    target = tmp_path / "virgin.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target).project.sequences[0]
    assert fresh.in_point.ticks == 254016000000
    assert fresh.out_point.ticks == 508032000000
    assert fresh.zero_point.ticks == 254016000000
    # Keys land at the head of the bag, in trio order.
    keys = [child.tag for child in fresh._element.find("Node/Properties")]
    assert keys[:3] == list(_TRIO)


def test_work_area_and_playhead_are_writable_when_unstored(tmp_path) -> None:
    # A sequence Premiere derived from a clip can carry no MZ.EditLine at
    # all; the getter reported 0 while the setter refused, so the pair has to
    # create its key like the in/out/zero trio does.
    application = py_premiere.parse(MINIMAL / "24_multicam.prproj")
    sequence = next(
        s
        for s in application.project.sequences
        if s._bag_element("MZ.EditLine") is None
    )
    sequence.playhead = Time(3 * 254016000000)
    sequence.work_area_in = Time(254016000000)
    sequence.work_area_out = Time(2 * 254016000000)
    target = tmp_path / "workarea.prproj"
    application.project.save(target)

    fresh = next(
        s
        for s in parse_project_fresh(target).project.sequences
        if s.name == sequence.name
    )
    assert fresh.playhead.ticks == 3 * 254016000000
    assert fresh.work_area_in.ticks == 254016000000
    assert fresh.work_area_out.ticks == 2 * 254016000000
    # Created keys keep Premiere's stored order around the ones already there.
    keys = [child.tag for child in fresh._element.find("Node/Properties")]
    present = [key for key in keys if key.startswith(("MZ.Work", "MZ.EditLine"))]
    assert present == ["MZ.WorkInPoint", "MZ.WorkOutPoint", "MZ.EditLine"]
    assert keys.index("MZ.EditLine") < keys.index("MZ.Sequence.VideoTimeDisplayFormat")


def test_display_format_still_raises_when_absent() -> None:
    # Non-trio keys keep the raise-on-absent contract.
    application = py_premiere.parse(MINIMAL / "04_sequence.prproj")
    sequence = application.project.sequences[0]
    with pytest.raises(ValueError):
        sequence._bag_write("MZ.DoesNotExist", 1)
