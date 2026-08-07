"""The ExtendScript parameters the signature audit found missing."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models.time import TICKS_PER_SECOND, Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"
ASSETS = SAMPLES_DIR / "models" / "assets"


def test_import_files_into_a_bin(tmp_path) -> None:
    # ExtendScript's importFiles(..., targetBin, ...).
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")
    root = application.project.root_item
    bin_a = root.children["Bin A"]
    item = application.project.import_files([ASSETS / "red_64x36.bmp"], bin_a)[0]
    assert item._parent is bin_a
    assert item.name in [child.name for child in bin_a.children]
    assert item.name not in [child.name for child in root.children]

    target = tmp_path / "binned.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_bin = fresh.project.root_item.children["Bin A"]
    assert "red_64x36.bmp" in [child.name for child in fresh_bin.children]
    assert "red_64x36.bmp" not in [
        child.name for child in fresh.project.root_item.children
    ]
    # The nested bin is untouched.
    assert "Bin A1" in [child.name for child in fresh_bin.children]


def test_import_files_defaults_to_the_root() -> None:
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")
    item = application.project.import_files([ASSETS / "red_64x36.bmp"])[0]
    assert item._parent is application.project.root_item


def test_import_files_rejects_a_non_bin() -> None:
    application = py_premiere.parse(MINIMAL / "02_bins.prproj")
    clip = application.project.import_files([ASSETS / "red_64x36.bmp"])[0]
    with pytest.raises(ValueError, match="bin"):
        application.project.import_files([ASSETS / "red_64x36.bmp"], clip)


def _subclip_shape(item):
    """(clip tags, sources carrying boundaries) for a subclip item."""
    document = item.project._document
    tags = sorted(element.tag for element in item._clip_elements)
    sources = []
    for element in item._clip_elements:
        core = element.find("Clip")
        reference = None if core is None else core.find("Source")
        if reference is None:
            continue
        source = document.resolve(reference)
        content = source.find("MediaSource/Content")
        if content is not None and content.find("StartBoundary") is not None:
            sources.append(source.tag)
    return tags, sorted(sources)


@pytest.mark.parametrize(
    ("take_video", "take_audio", "clips", "sources"),
    [
        (
            True,
            True,
            ["AudioClip", "VideoClip"],
            ["AudioMediaSource", "VideoMediaSource"],
        ),
        (True, False, ["VideoClip"], ["VideoMediaSource"]),
        (False, True, ["AudioClip"], ["AudioMediaSource"]),
    ],
)
def test_subclip_take_flags(take_video, take_audio, clips, sources) -> None:
    # Matches what Premiere's own createSubClip wrote for each flag pair
    # (sweep_audit_gaps.jsx): the untaken half's clip and source are gone,
    # and only the surviving source carries the boundary trio.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    source = application.project.import_files([ASSETS / "bars_64x36_av.mp4"])[0]
    sub = source.create_sub_clip(
        "part",
        Time(TICKS_PER_SECOND // 2),
        Time(TICKS_PER_SECOND),
        take_video=take_video,
        take_audio=take_audio,
    )
    assert _subclip_shape(sub) == (clips, sources)
    assert sub.is_subclip


def test_subclip_take_flags_round_trip(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    source = application.project.import_files([ASSETS / "bars_64x36_av.mp4"])[0]
    source.create_sub_clip(
        "video only",
        Time(0),
        Time(TICKS_PER_SECOND),
        take_audio=False,
    )
    target = tmp_path / "takes.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    # A subclip's live name lives on its master, so it reads back as the
    # name given to create_sub_clip.
    sub = fresh.project.root_item.children["video only"]
    assert sub.is_subclip
    assert [element.tag for element in sub._clip_elements] == ["VideoClip"]


def test_subclip_needs_at_least_one_half() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    source = application.project.import_files([ASSETS / "bars_64x36_av.mp4"])[0]
    with pytest.raises(ValueError, match="video, the audio, or both"):
        source.create_sub_clip(
            "none", Time(0), Time(TICKS_PER_SECOND), take_video=False, take_audio=False
        )


def test_save_in_place(tmp_path) -> None:
    # ExtendScript's save(), as opposed to saveAs(path).
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    target = tmp_path / "copy.prproj"
    application.project.save(target)
    application.project.sequences[0].name = "Renamed"
    application.project.save_in_place()
    assert application.project.path == target
    assert parse_project_fresh(target).project.sequences[0].name == "Renamed"
    # And `save` still refuses to clobber.
    with pytest.raises(FileExistsError):
        application.project.save(target)
