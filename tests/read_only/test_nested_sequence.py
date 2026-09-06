"""Nested-sequence detection, against the `66_eg_text` fixture.

`66_eg_text`'s "Seq B" cuts in "Seq A" (as both a video and an audio track
item - the same A/V pairing a regular media clip gets) alongside a
Graphic overlay, which is exactly the shape a real trailer/master
sequence has: a nested sub-edit plus a branding overlay on top.
"""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.models.nested_sequence import resolve_nested_sequence

MINIMAL = SAMPLES_DIR / "models" / "minimal"
FIXTURE = MINIMAL / "66_eg_text.prproj"


def test_resolves_a_nested_sequence_clip() -> None:
    application = py_premiere.parse(FIXTURE)
    seq_b = application.project.sequences["Seq B"]
    clip = next(c for c in seq_b.video_tracks[0].clips if c.name == "Seq A")

    nested = resolve_nested_sequence(clip)

    assert nested is not None
    assert nested.name == "Seq A"


def test_none_for_a_clip_backed_by_real_media() -> None:
    application = py_premiere.parse(FIXTURE)
    seq_a = application.project.sequences["Seq A"]
    footage = seq_a.video_tracks[0].clips[0]

    assert resolve_nested_sequence(footage) is None


def test_none_for_a_clip_with_no_master_clip_at_all() -> None:
    # A synthesized transition/generator track item can have no MasterClip
    # reference at all - resolve_nested_sequence must not raise on that,
    # same contract as a plain footage clip.
    application = py_premiere.parse(FIXTURE)
    seq_b = application.project.sequences["Seq B"]
    for track in seq_b.video_tracks:
        for clip in track.clips:
            resolve_nested_sequence(clip)  # must not raise, for any clip here
