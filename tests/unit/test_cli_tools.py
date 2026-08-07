"""Unit tests for pr-inspect and pr-compare on synthetic documents."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_premiere.cli.compare import main as compare_main
from py_premiere.cli.inspect import main as inspect_main
from py_premiere.cli.validate import _covered, shape_key
from py_premiere.cli.visualize import main as visualize_main

DOC_A = (
    b'<?xml version="1.0" encoding="UTF-8" ?>\n'
    b'<PremiereData Version="3">\n'
    b'\t<Project ObjectRef="1"/>\n'
    b'\t<Project ObjectID="1" ClassID="g" Version="38">\n'
    b"\t\t<Name>proj</Name>\n"
    b"\t</Project>\n"
    b'\t<Sequence ObjectUID="uid-1" Version="5">\n'
    b"\t\t<Name>Seq</Name>\n"
    b"\t\t<End>100</End>\n"
    b'\t\t<Owner ObjectRef="1"/>\n'
    b"\t</Sequence>\n"
    b"</PremiereData>\n\n"
)
# Same document after a simulated resave: ObjectIDs renumbered, End changed.
DOC_B = (
    DOC_A.replace(b'ObjectRef="1"', b'ObjectRef="7"')
    .replace(b'ObjectID="1"', b'ObjectID="7"')
    .replace(b"<End>100</End>", b"<End>200</End>")
)


@pytest.fixture()
def sample_pair(tmp_path: Path) -> tuple[Path, Path]:
    a = tmp_path / "a.prproj"
    b = tmp_path / "b.prproj"
    a.write_bytes(DOC_A)
    b.write_bytes(DOC_B)
    return a, b


def test_compare_reports_value_change_and_suppresses_churn(
    sample_pair: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    a, b = sample_pair
    assert compare_main([str(a), str(b)]) == 1
    out = capsys.readouterr().out
    assert "'100' vs '200'" in out
    assert "churn suppressed" in out
    # The renumbered ObjectID/ObjectRef must not surface as differences.
    assert "@ObjectID" not in out
    assert "'1' vs '7'" not in out


def test_compare_identical_files_exit_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = tmp_path / "a.prproj"
    b = tmp_path / "b.prproj"
    a.write_bytes(DOC_A)
    b.write_bytes(DOC_A)
    assert compare_main([str(a), str(b)]) == 0
    assert "0 differing object(s)" in capsys.readouterr().out


def test_compare_show_churn_reports_renumbering(
    sample_pair: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    a, b = sample_pair
    assert compare_main([str(a), str(b), "--show-churn"]) == 1
    assert "@ObjectID: '1' vs '7'" in capsys.readouterr().out


def test_inspect_summary_and_list(
    sample_pair: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    a, _ = sample_pair
    assert inspect_main([str(a)]) == 0
    out = capsys.readouterr().out
    assert "3 top-level objects" in out
    assert "Sequence" in out
    assert inspect_main([str(a), "--list"]) == 0
    out = capsys.readouterr().out
    assert "uid-1" in out
    assert "'Seq'" in out


def test_visualize_smoke(
    sample_pair: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    a, _ = sample_pair
    assert visualize_main([str(a)]) == 0
    out = capsys.readouterr().out
    assert "1 sequence(s)" in out
    assert "Seq" in out


def test_inspect_dump_by_uid(
    sample_pair: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    a, _ = sample_pair
    assert inspect_main([str(a), "--dump", "uid-1"]) == 0
    out = capsys.readouterr().out
    assert out.startswith('<Sequence ObjectUID="uid-1"')
    assert "<End>100</End>" in out


def _ref_doc(first: bytes, second: bytes) -> bytes:
    # Two UID-less holders, alike but for the leaf each points at.
    return (
        b'<?xml version="1.0" encoding="UTF-8" ?>\n'
        b'<PremiereData Version="3">\n'
        b'\t<Leaf ObjectID="10" Version="1">\n'
        b"\t\t<Name>alpha</Name>\n"
        b"\t</Leaf>\n"
        b'\t<Leaf ObjectID="11" Version="1">\n'
        b"\t\t<Name>beta</Name>\n"
        b"\t</Leaf>\n"
        b'\t<Holder ObjectID="1" Version="1">\n'
        b'\t\t<Points ObjectRef="' + first + b'"/>\n'
        b"\t</Holder>\n"
        b'\t<Holder ObjectID="2" Version="1">\n'
        b'\t\t<Points ObjectRef="' + second + b'"/>\n'
        b"\t</Holder>\n"
        b"</PremiereData>\n\n"
    )


def test_compare_matches_uidless_objects_by_what_they_reference(
    tmp_path, capsys
) -> None:
    # The same two holders in the opposite order. Matching them by tag order
    # would pair alpha against beta and report two phantom differences;
    # ref-aware signatures pair each holder with its own target.
    path_a = tmp_path / "a.prproj"
    path_b = tmp_path / "b.prproj"
    path_a.write_bytes(_ref_doc(b"10", b"11"))
    path_b.write_bytes(_ref_doc(b"11", b"10"))

    assert compare_main([str(path_a), str(path_b)]) == 0
    out = capsys.readouterr().out
    assert "alpha" not in out
    assert "beta" not in out


def test_compare_still_reports_a_genuinely_repointed_reference(
    tmp_path, capsys
) -> None:
    # Ref-awareness must not silence a real change: here the SECOND holder
    # is gone and the first points somewhere new.
    path_a = tmp_path / "a.prproj"
    path_b = tmp_path / "b.prproj"
    path_a.write_bytes(_ref_doc(b"10", b"10"))
    path_b.write_bytes(_ref_doc(b"11", b"11"))

    assert compare_main([str(path_a), str(path_b)]) == 1
    out = capsys.readouterr().out
    assert "alpha" in out and "beta" in out


def test_compare_aligns_children_instead_of_shifting(tmp_path, capsys) -> None:
    # An element inserted mid-list must be reported once, not cascade into a
    # `tag <A> vs <B>` line for every sibling after it.
    before = (
        b'<?xml version="1.0" encoding="UTF-8" ?>\n'
        b'<PremiereData Version="3">\n'
        b'\t<Param ObjectID="1" Version="1">\n'
        b"\t\t<Name>Mute</Name>\n"
        b"\t\t<RangeLocked>false</RangeLocked>\n"
        b"\t</Param>\n"
        b"</PremiereData>\n\n"
    )
    after = before.replace(
        b"\t\t<Name>Mute</Name>\n",
        b"\t\t<StartKeyframe>0,true</StartKeyframe>\n"
        b"\t\t<CurrentValue>true</CurrentValue>\n"
        b"\t\t<Name>Mute</Name>\n",
    )
    path_a = tmp_path / "a.prproj"
    path_b = tmp_path / "b.prproj"
    path_a.write_bytes(before)
    path_b.write_bytes(after)

    assert compare_main([str(path_a), str(path_b)]) == 1
    out = capsys.readouterr().out
    assert "only in file2 <StartKeyframe>" in out
    assert "only in file2 <CurrentValue>" in out
    # The shared children must NOT be reported as tag mismatches.
    assert "tag <Name>" not in out
    assert "tag <RangeLocked>" not in out
    assert "unpaired child" not in out


def test_validate_shape_key_maps_display_paths_to_ground_truth_keys() -> None:
    assert shape_key("project", "documentID") == "documentID"
    assert shape_key("rootItem/[0]", "colorLabel") == "rootItem.children[].colorLabel"
    assert (
        shape_key("rootItem/[0]/[2]", "name") == "rootItem.children[].children[].name"
    )
    assert (
        shape_key("sequences[0] ('Seq A')/audioTracks[1]", "isMuted")
        == "sequences[].audioTracks[].isMuted"
    )
    assert (
        shape_key("sequences[0] ('Seq A')/videoTracks[0]/clips[3]", "name")
        == "sequences[].videoTracks[].clips[].name"
    )


def test_validate_covered_accepts_asserted_ancestors() -> None:
    asserted = {"clips[].inPoint", "sequences[].audioTracks[].isMuted"}
    assert _covered("clips[].inPoint.ticks", asserted)
    assert _covered("clips[].inPoint.seconds", asserted)
    assert _covered("sequences[].audioTracks[].isMuted", asserted)
    assert not _covered("clips[].outPoint.ticks", asserted)
