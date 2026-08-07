"""Essential Graphics text decodes through the caption FlatBuffer (66)."""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def test_source_text_reads_the_typed_text() -> None:
    # 66_eg_text: a Type-tool graphic with the text `py`. The Source Text
    # parameter's StartKeyframeValue is the same FormattedTextData
    # FlatBuffer captions use, so the plain text reads straight out.
    application = py_premiere.parse(MINIMAL / "66_eg_text.prproj")
    text_component = next(
        clip.components["Text"]
        for sequence in application.project.sequences
        for clip in sequence.clips
        if "Text" in clip.components
    )
    assert text_component.match_name == "AE.ADBE Text"
    source_text = next(
        p for p in text_component.properties if p.display_name == "Source Text"
    )
    assert source_text.text == "py"
    # A non-text parameter reads None.
    position = next(
        p for p in text_component.properties if p.display_name == "Position"
    )
    assert position.text is None
