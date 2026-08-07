"""Caption track parsing against the `29_captions` fixture."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.enums import CaptionFormat
from py_premiere.models import CaptionTrack

MINIMAL = SAMPLES_DIR / "models" / "minimal"
FIXTURE = MINIMAL / "29_captions.prproj"
# The .srt that was imported to build the fixture:
#   1  00:00:00,000 --> 00:00:01,000  Hello from py-premiere
#   2  00:00:01,000 --> 00:00:02,000  Second caption line
SECOND = 254016000000
FRAME = 8475667200


def _track() -> CaptionTrack:
    application = py_premiere.parse(FIXTURE)
    tracks = application.project.sequences[0].caption_tracks
    assert len(tracks) == 1
    return tracks[0]


def test_caption_track_identity() -> None:
    track = _track()
    assert track.id == 1
    assert track.index == 0
    assert track.sequence.name == "Seq A"


def test_caption_text_decoded() -> None:
    captions = _track().captions
    assert [caption.text for caption in captions] == [
        "Hello from py-premiere",
        "Second caption line",
    ]


def test_caption_source_times_match_the_srt() -> None:
    first, second = _track().captions
    assert first.source_start.ticks == 0
    assert first.source_end.ticks == SECOND
    assert second.source_start.ticks == SECOND
    assert second.source_end.ticks == 2 * SECOND


def test_caption_timeline_times_are_frame_aligned() -> None:
    # The timeline placement snaps to whole 29.97 frames, so it does NOT
    # equal the source times the .srt states.
    first, second = _track().captions
    assert first.start.ticks == 0
    assert first.end.ticks == 30 * FRAME
    assert second.start.ticks == 30 * FRAME
    assert second.end.ticks == 60 * FRAME
    assert first.end.ticks != first.source_end.ticks
    assert first.track is second.track


def test_sequence_without_captions_has_no_caption_tracks() -> None:
    # Every sequence carries the data track group; only an imported caption
    # stream puts a track in it.
    application = py_premiere.parse(FIXTURE)
    assert application.project.sequences[1].caption_tracks == []
    other = py_premiere.parse(MINIMAL / "06_api.prproj")
    assert all(sequence.caption_tracks == [] for sequence in other.project.sequences)


def test_caption_track_format() -> None:
    # 29_captions is CEA-708 (`Format` 2); converting the track to
    # Subtitle DELETES the element (64_caption_style), and an absent
    # Format is exactly how the API's SUBTITLE constant (0) is stored.
    for name, expected in (
        ("29_captions", CaptionFormat.CEA_708),
        ("64_caption_style", CaptionFormat.SUBTITLE),
    ):
        application = py_premiere.parse(MINIMAL / f"{name}.prproj")
        track = next(
            s.caption_tracks[0]
            for s in application.project.sequences
            if s.caption_tracks
        )
        assert track.format == expected
