"""Placing both halves of an A/V item as a linked pair.

The shape to match is the `Link` Premiere writes for its own linked
placements: `06_api`'s Seq B holds one binding the two halves of the
nested Seq A.
"""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models.time import TICKS_PER_SECOND, Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"
ASSETS = SAMPLES_DIR / "models" / "assets"


def _links(application, sequence_name):
    """(link element, the track items it binds) for each link."""
    project = application.project
    sequence = project.sequences[sequence_name]
    document = project._document
    out = []
    for entry in sequence._element.findall(
        "PersistentGroupContainer/LinkContainer/Links/Link"
    ):
        link = document.resolve(entry)
        bound = [
            document.resolve(reference)
            for reference in link.findall("TrackItemGroup/TrackItems/TrackItem")
        ]
        out.append((link, bound))
    return out


def _import_av(application):
    return application.project.import_files([ASSETS / "bars_64x36_av.mp4"])[0]


def test_link_matches_the_shape_premiere_writes() -> None:
    # Premiere's own link, for reference: two track items, in order.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    ((link, bound),) = _links(application, "Seq B")
    assert link.tag == "Link"
    assert [element.tag for element in bound] == [
        "VideoClipTrackItem",
        "AudioClipTrackItem",
    ]


def test_add_linked_clip_binds_both_halves(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    item = _import_av(application)
    video, audio = application.project.sequences["Seq A"].add_linked_clip(
        item, Time(6 * TICKS_PER_SECOND)
    )
    assert video.start.ticks == audio.start.ticks == 6 * TICKS_PER_SECOND
    assert video.end.ticks == audio.end.ticks

    target = tmp_path / "linked.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    links = _links(fresh, "Seq A")
    assert len(links) == 1
    _, bound = links[0]
    assert [element.tag for element in bound] == [
        "VideoClipTrackItem",
        "AudioClipTrackItem",
    ]
    # The link points at the placements themselves, not at copies.
    placed = {
        fresh.project.sequences["Seq A"]
        .video_tracks[0]
        .clips[-1]
        ._element.get("ObjectID"),
        fresh.project.sequences["Seq A"]
        .audio_tracks[0]
        .clips[-1]
        ._element.get("ObjectID"),
    }
    assert {element.get("ObjectID") for element in bound} == placed


def test_a_second_link_appends_rather_than_replacing(tmp_path) -> None:
    # Seq B already holds one link; a new pair must not disturb it.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    item = _import_av(application)
    application.project.sequences["Seq B"].add_linked_clip(
        item, Time(6 * TICKS_PER_SECOND)
    )
    target = tmp_path / "two_links.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    links = _links(fresh, "Seq B")
    assert len(links) == 2
    assert [
        entry.get("Index")
        for entry in fresh.project.sequences["Seq B"]._element.findall(
            "PersistentGroupContainer/LinkContainer/Links/Link"
        )
    ] == ["0", "1"]


def test_add_linked_clip_needs_both_streams() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    still = application.project.root_item.children["red_64x36.bmp"]
    with pytest.raises(ValueError, match="video and audio"):
        application.project.sequences["Seq A"].add_linked_clip(still)


def test_add_linked_clip_checks_the_track_indices() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    item = _import_av(application)
    sequence = application.project.sequences["Seq A"]
    with pytest.raises(ValueError, match="video track"):
        sequence.add_linked_clip(item, video_track=99)
    with pytest.raises(ValueError, match="audio track"):
        sequence.add_linked_clip(item, audio_track=99)
