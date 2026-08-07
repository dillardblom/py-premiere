"""Mutation round-trips through the write API (save, re-parse fresh)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.models import Time

FIXTURE = SAMPLES_DIR / "models" / "minimal" / "04_sequence.prproj"
FEATURES = SAMPLES_DIR / "models" / "minimal" / "05_features.prproj"


@pytest.fixture()
def project_copy(tmp_path: Path) -> Path:
    copy = tmp_path / FIXTURE.name
    shutil.copy(FIXTURE, copy)
    return copy


def _first_clip(application: py_premiere.models.Application):  # type: ignore[name-defined]
    for track in application.project.sequences[0].video_tracks:
        if track.clips:
            return track.clips[0]
    raise AssertionError("fixture has no video clip")


def test_save_without_mutation_is_identity(project_copy: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.prproj"
    py_premiere.parse(project_copy).project.save(out)
    assert out.read_bytes() == project_copy.read_bytes()


def test_save_refuses_overwrite(project_copy: Path) -> None:
    application = py_premiere.parse(project_copy)
    with pytest.raises(FileExistsError):
        application.project.save(project_copy)


def test_rename_sequence_round_trips(project_copy: Path, tmp_path: Path) -> None:
    out = tmp_path / "renamed.prproj"
    application = py_premiere.parse(project_copy)
    application.project.sequences[0].name = "Renamed & <Checked>"
    application.project.save(out)
    fresh = py_premiere.parse(out)
    assert fresh.project.sequences[0].name == "Renamed & <Checked>"


def test_rename_items_round_trips(project_copy: Path) -> None:
    application = py_premiere.parse(project_copy)
    clip = _first_clip(application)
    clip.name = "my clip"
    root = application.project.root_item
    assert root is not None
    root.children[0].name = "my item"
    out = project_copy.with_name("renamed_items.prproj")
    application.project.save(out)
    fresh = py_premiere.parse(out)
    assert _first_clip(fresh).name == "my clip"
    fresh_root = fresh.project.root_item
    assert fresh_root is not None
    assert fresh_root.children[0].name == "my item"


def test_time_fields_round_trip(project_copy: Path) -> None:
    application = py_premiere.parse(project_copy)
    clip = _first_clip(application)
    timebase = application.project.sequences[0].timebase
    assert timebase is not None
    # start is elided (0) in the fixture; writing it exercises element
    # creation with formatting preservation.
    assert clip.start == Time(0)
    clip.start = Time(10 * timebase)
    clip.end = Time(20 * timebase)
    clip.out_point = Time(clip.in_point.ticks + 10 * timebase)
    out = project_copy.with_name("times.prproj")
    application.project.save(out)
    fresh = py_premiere.parse(out)
    fresh_clip = _first_clip(fresh)
    assert fresh_clip.start == Time(10 * timebase)
    assert fresh_clip.end == Time(20 * timebase)
    assert fresh_clip.duration == Time(10 * timebase)
    assert fresh_clip.out_point.ticks - fresh_clip.in_point.ticks == 10 * timebase


def test_marker_mutation_round_trips(tmp_path: Path) -> None:
    copy = tmp_path / FEATURES.name
    shutil.copy(FEATURES, copy)
    application = py_premiere.parse(copy)
    marker = application.project.sequences[0].markers[0]
    assert marker.name == "seq marker"
    assert marker.type == "Comment"
    marker.name = "renamed marker"
    marker.comments = "updated"
    marker.start = Time(py_premiere.TICKS_PER_SECOND)
    out = tmp_path / "markers.prproj"
    application.project.save(out)
    fresh = py_premiere.parse(out)
    fresh_marker = fresh.project.sequences[0].markers[0]
    assert fresh_marker.name == "renamed marker"
    assert fresh_marker.comments == "updated"
    assert fresh_marker.start == Time(py_premiere.TICKS_PER_SECOND)
    assert fresh_marker.type == "Comment"
    assert fresh_marker.guid == marker.guid


def test_keyframes_read() -> None:
    application = py_premiere.parse(FEATURES)
    clip = _first_clip(application)
    opacity = next(c for c in clip.components if c.display_name == "Opacity")
    param = next(p for p in opacity.properties if p.display_name == "Opacity")
    assert param.is_time_varying
    keys = param.keys
    assert len(keys) == 2
    assert param.get_value_at_key(keys[0]) == 100.0
    assert param.get_value_at_key(keys[1]) == 25.5


def test_read_only_attributes_raise(project_copy: Path) -> None:
    application = py_premiere.parse(project_copy)
    sequence = application.project.sequences[0]
    clip = _first_clip(application)
    for target, attribute, value in [
        (application, "project", None),
        (application.project, "name", "x"),
        (application.project, "path", "x"),
        (sequence, "timebase", 1),
        (sequence, "sequence_id", "x"),
        (sequence.video_tracks[0], "id", 1),
        (sequence.video_tracks[0], "media_type", "Video"),
        (clip, "duration", Time(0)),
    ]:
        with pytest.raises(AttributeError):
            setattr(target, attribute, value)


def test_validation_rejects_bad_values(project_copy: Path) -> None:
    application = py_premiere.parse(project_copy)
    sequence = application.project.sequences[0]
    clip = _first_clip(application)
    with pytest.raises(TypeError, match="expected a string"):
        sequence.name = 123  # type: ignore[assignment]
    with pytest.raises(TypeError, match="expected a Time"):
        clip.start = 5  # type: ignore[assignment]
    with pytest.raises(TypeError, match="expected an integer"):
        Time("100")  # type: ignore[arg-type]
