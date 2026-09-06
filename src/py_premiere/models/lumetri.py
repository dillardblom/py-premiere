"""Reading a Lumetri Color effect's Basic Correction values.

Lumetri's Basic Correction panel (white balance, tone, saturation) is the
one section most graded clips actually use, and the one whose numbers are
plain scalars - unlike Creative's LUT index, Curves' point tables or HSL
Secondary's qualifier ranges, none of which name a portable target the way
a temperature/exposure/contrast slider does.

The component's parameter list is NOT uniquely keyed by display name:
`Temperature`, `Tint`, `Contrast` and `Saturation` each reappear inside
the Creative and HSL Secondary sections (verified against
`67_lumetri_exposure`, whose HSL Secondary "Correction" sub-panel repeats
Temperature/Tint/Contrast/Sharpen/Saturation). Reading by name alone would
silently risk picking up the wrong section's value. Basic Correction is
always the first section and Creative always the second - fixed by
Adobe's own panel layout, not user-configurable - so the slice between
those two section toggles is what this reads from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from .component import ComponentParam
    from .track_item import TrackItem

_LUMETRI_MATCH_NAME = "AE.ADBE Lumetri"
_SECTION_START = "Basic Correction"
_SECTION_END = "Creative"

#: Adobe's own defaults for an untouched Basic Correction panel - used only
#: if a slot is somehow absent from an otherwise-matched section, which has
#: not been observed on any real or fixture project so far.
_DEFAULTS = {
    "Temperature": 0.0,
    "Tint": 0.0,
    "Saturation": 100.0,
    "Exposure": 0.0,
    "Contrast": 0.0,
    "Highlights": 0.0,
    "Shadows": 0.0,
    "Whites": 0.0,
    "Blacks": 0.0,
}


class LumetriBasicCorrection(NamedTuple):
    """Lumetri's Basic Correction panel values, Adobe's own scale/range."""

    temperature: float
    tint: float
    saturation: float
    exposure: float
    contrast: float
    highlights: float
    shadows: float
    whites: float
    blacks: float


def _basic_correction_slice(properties: list[ComponentParam]) -> list[ComponentParam]:
    names = [p.display_name for p in properties]
    try:
        start = names.index(_SECTION_START)
        end = names.index(_SECTION_END, start + 1)
    except ValueError:
        return []
    return properties[start + 1 : end]


def read_lumetri_basic_correction(clip: TrackItem) -> LumetriBasicCorrection | None:
    """`clip`'s Lumetri Basic Correction values, or `None` if it has none.

    `None` covers any clip without a Lumetri Color effect at all - most
    connected/adjustment-layer clips carry some OTHER effect (a generic
    'Adjustment Layer' with no Lumetri on it, a blur, a vignette, ...),
    which this makes no attempt to read.
    """
    for component in clip.components:
        if component.match_name != _LUMETRI_MATCH_NAME:
            continue
        section = _basic_correction_slice(list(component.properties))
        if not section:
            continue
        values = dict(_DEFAULTS)
        seen: set[str] = set()
        for param in section:
            name = param.display_name
            if name in values and name not in seen:
                value = param.value
                if isinstance(value, (int, float)):
                    values[name] = float(value)
                seen.add(name)
        return LumetriBasicCorrection(
            temperature=values["Temperature"],
            tint=values["Tint"],
            saturation=values["Saturation"],
            exposure=values["Exposure"],
            contrast=values["Contrast"],
            highlights=values["Highlights"],
            shadows=values["Shadows"],
            whites=values["Whites"],
            blacks=values["Blacks"],
        )
    return None
