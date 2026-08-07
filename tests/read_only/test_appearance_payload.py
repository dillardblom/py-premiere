"""The graphics `Appearance` blob is a FormattedTextData document.

Same container as a caption's styled text - a `uint64` length prefix
(payload minus 12), the `0x11223344` magic, then the FlatBuffer - so the
caption decoder reads it as-is rather than needing its own.

The only corpus occurrences are in the template projects, which are not
committed, so this skips without them.
"""

from __future__ import annotations

import struct

import pytest
from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.models import caption

#: Premiere's own resave of template 523, the one corpus file that
#: carries `Appearance` payloads.
FIXTURE = SAMPLES_DIR / "resaves" / "Abstract Slideshow_resave.prproj"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="the template resaves are local-only"
)


def _appearance_payloads(limit: int = 3):
    application = py_premiere.parse(FIXTURE)
    document = application.project._document
    out = []
    for element in document.root:
        if not element.tag.startswith("Arb"):
            continue
        if (element.findtext("Name") or "") != "Appearance":
            continue
        value = element.find("StartKeyframeValue")
        payload = document.payload(value) if value is not None else None
        if payload:
            out.append(payload)
            if len(out) >= limit:
                break
    return out


def test_appearance_uses_the_caption_text_container() -> None:
    payloads = _appearance_payloads()
    assert payloads, "the fixture should carry Appearance payloads"
    for payload in payloads:
        prefix, magic = struct.unpack_from("<QI", payload, 0)
        assert prefix == len(payload) - 12
        assert magic == 0x11223344
        # And it walks: the caption decoder finds a document table with
        # populated slots in the same numbering it uses for text.
        table = caption._document_table(payload)
        slots = [
            slot for slot in range(24) if caption._field_offset(payload, table, slot)
        ]
        assert slots, "an Appearance document with no populated slot"
