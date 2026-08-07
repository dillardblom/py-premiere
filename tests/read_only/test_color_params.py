"""Color param decode on real data (local-only resave; skipped on CI)."""

from __future__ import annotations

from helpers import SAMPLES_DIR, require_sample

import py_premiere
from py_premiere.models import Color

RESAVE = SAMPLES_DIR / "resaves" / "Abstract Slideshow_resave.prproj"


def test_color_params_decode() -> None:
    application = py_premiere.parse(require_sample(RESAVE))
    colors = []
    for sequence in application.project.sequences:
        for track in sequence.video_tracks:
            for clip in track.clips:
                for component in clip.components:
                    for param in component.properties:
                        color = param.color
                        if color is not None:
                            colors.append(color)
    assert colors
    for color in colors:
        assert isinstance(color, Color)
        assert all(0 <= channel <= 255 for channel in color)
    # The Drop Shadow / Tint colors verified against UXP appear here.
    assert Color(163, 247, 143, 255) in colors


def test_non_color_param_returns_none() -> None:
    application = py_premiere.parse(
        SAMPLES_DIR / "models" / "minimal" / "09_keyframes.prproj"
    )
    clip = application.project.sequences[0].video_tracks[0].clips[0]
    opacity = next(c for c in clip.components if c.match_name == "AE.ADBE Opacity")
    assert opacity.properties[0].color is None
