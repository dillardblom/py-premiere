"""The FormattedTextData text splice, against Premiere's own payloads."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.models.caption import (
    decode_caption_text,
    read_font_size,
    replace_payload_text,
)

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _payloads(fixture: str) -> dict[str, bytes]:
    application = py_premiere.parse(MINIMAL / f"{fixture}.prproj")
    document = application.project._document
    found = {}
    for element in document.root:
        if element.tag == "Block":
            data = element.find("FormattedTextData")
            found[element.get("ObjectID")] = document.payload(data)
    return found


def test_retexting_one_block_rebuilds_the_other_byte_exactly() -> None:
    # 29_captions holds two blocks that differ ONLY in their cue text
    # ("Hello from py-premiere" / "Second caption line"), so splicing one
    # into the other must reproduce Premiere's bytes in both directions -
    # the strings differ in length, exercising the offset shifts.
    blocks = _payloads("29_captions")
    first, second = blocks["97"], blocks["98"]
    assert decode_caption_text(first) == "Hello from py-premiere"
    assert decode_caption_text(second) == "Second caption line"
    assert replace_payload_text(first, "Second caption line") == second
    assert replace_payload_text(second, "Hello from py-premiere") == first


def test_retexting_preserves_styling() -> None:
    # A restyled payload (75 pt) keeps its size across a text change.
    blocks = _payloads("80_subtitle_font_size_75")
    styled = blocks["152"]
    assert read_font_size(styled) == 75.0
    rewritten = replace_payload_text(styled, "Totally different wording here")
    assert decode_caption_text(rewritten) == "Totally different wording here"
    assert read_font_size(rewritten) == 75.0


@pytest.mark.parametrize(
    "text",
    ["a", "ab", "abc", "abcd", "x" * 200, "two\nlines", "accents: é and ü"],
)
def test_retexting_round_trips_any_length(text: str) -> None:
    # Every padding remainder, plus multi-line and non-ASCII text.
    payload = _payloads("29_captions")["97"]
    rewritten = replace_payload_text(payload, text)
    assert decode_caption_text(rewritten) == text
    # The buffer's own length prefix stays in step with the bytes (it
    # counts everything after the prefix and the magic).
    assert int.from_bytes(rewritten[:8], "little") == len(rewritten) - 12
    # And the result re-splices cleanly (the offsets survived).
    again = replace_payload_text(rewritten, "back to something else")
    assert decode_caption_text(again) == "back to something else"


def test_empty_text_is_refused() -> None:
    # The format identifies its text as the LAST length-prefixed string, so
    # an empty one would read back as the font name that precedes it.
    payload = _payloads("29_captions")["97"]
    with pytest.raises(ValueError, match="empty"):
        replace_payload_text(payload, "")


def test_retexting_the_eg_payload() -> None:
    # The Source Text buffer is the same family with a leaner style table.
    application = py_premiere.parse(MINIMAL / "66_eg_text.prproj")
    document = application.project._document
    param = next(
        p
        for sequence in application.project.sequences
        for clip in sequence.clips
        if "Text" in clip.components
        for p in clip.components["Text"].properties
        if p.display_name == "Source Text"
    )
    payload = document.payload(param._element.find("StartKeyframeValue"))
    assert decode_caption_text(payload) == "py"
    rewritten = replace_payload_text(payload, "hello graphics")
    assert decode_caption_text(rewritten) == "hello graphics"
    assert int.from_bytes(rewritten[:8], "little") == len(rewritten) - 12
