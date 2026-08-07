"""SRT parsing and caption payload synthesis (no sample project)."""

from __future__ import annotations

import pytest

from py_premiere.models.caption import decode_caption_text
from py_premiere.models.caption_builder import build_caption_payload, parse_srt

_TICKS_PER_MS = 254016000


def test_parse_srt_cues() -> None:
    cues = parse_srt(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n\n"
        "2\n00:00:01,500 --> 00:01:02,250\nSecond line\n"
    )
    assert [c.text for c in cues] == ["Hello", "Second line"]
    assert cues[0].start == 0
    assert cues[0].end == 1000 * _TICKS_PER_MS
    assert cues[1].start == 1500 * _TICKS_PER_MS
    assert cues[1].end == 62250 * _TICKS_PER_MS


def test_parse_srt_tolerates_optional_indexes_and_crlf() -> None:
    cues = parse_srt(
        "00:00:00.000 --> 00:00:01.000\r\nNo index, dot millis\r\n\r\n"
        "7\r\n00:00:02,000 --> 00:00:03,000\r\nTwo\r\nlines\r\n"
    )
    assert cues[0].text == "No index, dot millis"
    assert cues[1].text == "Two\nlines"


def test_parse_srt_rejects_junk() -> None:
    with pytest.raises(ValueError, match="no cues"):
        parse_srt("not a subtitle file")
    with pytest.raises(ValueError, match="ends before"):
        parse_srt("1\n00:00:02,000 --> 00:00:01,000\nBackwards\n")


@pytest.mark.parametrize(
    "text",
    [
        "Hello from py-premiere",  # the template text itself
        "Second caption line",  # the fixture's other payload
        "x",  # minimal
        "An appreciably longer caption line than the template held",
        "Accents éèê and a\nline break",
    ],
)
def test_payload_round_trips_through_the_reader(text: str) -> None:
    # The existing FlatBuffer reader is the oracle: whatever py writes must
    # decode back to the exact text.
    assert decode_caption_text(build_caption_payload(text)) == text
