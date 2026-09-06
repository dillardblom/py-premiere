"""Essential Graphics text reading, against the `66_eg_text` fixture.

Also confirms the negative case against a real archive project's legacy
Titler clip: `read_graphic_text` must return `None` rather than raise or
false-match, since a legacy title has no `AE.ADBE Text` component at all.
"""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.models import read_graphic_text

MINIMAL = SAMPLES_DIR / "models" / "minimal"
FIXTURE = MINIMAL / "66_eg_text.prproj"


def test_reads_text_font_and_size() -> None:
    application = py_premiere.parse(FIXTURE)
    sequence = application.project.sequences["Seq B"]
    graphic = next(c for c in sequence.video_tracks[1].clips if c.name == "Graphic")

    info = read_graphic_text(graphic)

    assert info is not None
    assert info.text == "py"
    assert info.font_family == "LucidaConsole"
    assert info.font_size > 0


def test_none_for_a_clip_with_no_text_component() -> None:
    application = py_premiere.parse(FIXTURE)
    sequence = application.project.sequences["Seq A"]
    footage = sequence.video_tracks[0].clips[0]

    assert read_graphic_text(footage) is None
