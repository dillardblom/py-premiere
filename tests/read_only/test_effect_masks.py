"""Effect masks against the hand-built `26_effect_mask` fixture.

Masks have no scripting API in either DOM, so the fixture was drawn by hand:
a Gaussian Blur with an ellipse mask feathered to 25. A mask is itself a
component (`AE.ADBE AEMask2`) and appears in TWO roles - attached to an
effect (that effect's `sub_components`) and applied to the whole clip (the
track item's `selection_components`).
"""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"

MASK_MATCH_NAME = "AE.ADBE AEMask2"


def _masked_clip():
    application = py_premiere.parse(MINIMAL / "26_effect_mask.prproj")
    for sequence in application.project.sequences:
        for track in sequence.video_tracks:
            for clip in track.clips:
                if clip.components:
                    return clip
    raise AssertionError("no clip with components in the fixture")


def test_mask_attached_to_an_effect() -> None:
    clip = _masked_clip()
    blur = clip.components[0]
    assert blur.display_name == "Gaussian Blur"
    assert [s.match_name for s in blur.sub_components] == [MASK_MATCH_NAME]

    mask = blur.sub_components[0]
    values = {p.display_name: p.value for p in mask.properties if p.display_name}
    # The feather the fixture was drawn with, read back through the ordinary
    # parameter decoding - a mask needs no special-casing beyond being found.
    assert values["Feather"] == 25.0
    assert values["Opacity"] == 100.0
    assert values["Expansion"] == 0.0


def test_clip_level_mask() -> None:
    clip = _masked_clip()
    assert [c.match_name for c in clip.selection_components] == [MASK_MATCH_NAME]


def test_unmasked_clips_have_neither() -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    for sequence in application.project.sequences:
        for track in sequence.video_tracks + sequence.audio_tracks:
            for clip in track.clips:
                assert clip.selection_components == []
                for component in clip.components:
                    assert component.sub_components == []
