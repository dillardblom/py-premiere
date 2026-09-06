"""Reading an Essential Graphics/Type-tool clip's on-screen text.

A Type-tool text clip carries an `AE.ADBE Text` component whose `Source
Text` parameter holds the same `FormattedTextData` payload format the
caption track's sources use (see `caption.py` - `graphic_builder.py`
confirms both are built on Premiere's same synthetic-media generator).
This reuses those existing payload decoders rather than duplicating them.

Legacy Titler clips carry no such component: their text lives inside an
`ImporterPrefs` blob whose payload is stamped `CompressedTitle`, an
undocumented, compressed, proprietary encoding this does not read. For
those, `read_graphic_text` returns `None` - there is nothing here to
recover it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from .caption import (
    _STYLE_FILL_SLOT,
    decode_caption_text,
    read_font_family,
    read_font_size,
    read_style_color,
)
from .color import Color

if TYPE_CHECKING:
    from .track_item import TrackItem

_TEXT_MATCH_NAME = "AE.ADBE Text"
_SOURCE_TEXT_PARAM_NAME = "Source Text"


class GraphicText(NamedTuple):
    """The readable text content of an Essential Graphics text clip."""

    text: str
    font_family: str
    font_size: float
    fill_color: Color | None


def read_graphic_text(clip: TrackItem) -> GraphicText | None:
    """`clip`'s Essential Graphics text content, or `None` if it has none.

    `None` covers every clip that is not a Type-tool text clip at all
    (ordinary footage, a nested sequence, an adjustment layer, a legacy
    Titler clip, ...) - there is no separate error path, since from the
    caller's side all of those look the same: nothing to show.
    """
    for component in clip.components:
        if component.match_name != _TEXT_MATCH_NAME:
            continue
        for param in component.properties:
            if param.display_name != _SOURCE_TEXT_PARAM_NAME:
                continue
            value_element = param._element.find("StartKeyframeValue")
            if value_element is None:
                continue
            document = component.track_item.track.sequence.project._document
            payload = document.payload(value_element)
            if payload is None:
                continue
            return GraphicText(
                text=decode_caption_text(payload),
                font_family=read_font_family(payload),
                font_size=read_font_size(payload),
                fill_color=read_style_color(payload, _STYLE_FILL_SLOT),
            )
    return None
