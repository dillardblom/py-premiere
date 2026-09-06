"""Detecting and resolving a track item's underlying nested sequence.

A clip whose source is another `Sequence` (rather than a media file) is
NOT always reachable through `TrackItem.project_item`: Premiere lets a
sequence stay in use on a timeline after its panel item has been removed
from the project bin - the master clip is fine, only its `ProjectItem`
wrapper is gone. Confirmed on a real 2014 archive project, where a used,
top-level nested sequence resolved `project_item` to `None` - a check
through `project_item.is_sequence` alone would have missed it entirely.

This resolves the same `MasterClip -> Clip -> Source ->
SequenceSource/Sequence` chain `parsers/project.py` walks for a bin item,
directly off the track item's own master clip, so detection does not
depend on the panel item still existing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .project_item import clip_core

if TYPE_CHECKING:
    from .sequence import Sequence
    from .track_item import TrackItem


def _master_sequence_uid(clip: TrackItem) -> str | None:
    master_ref = clip._subclip_element.find("MasterClip")
    if master_ref is None:
        return None
    document = clip.track.sequence.project._document
    master = document.resolve(master_ref)
    for clip_ref in master.findall("Clips/Clip"):
        core = clip_core(document.resolve(clip_ref))
        if core is None:
            continue
        source_ref = core.find("Source")
        if source_ref is None:
            continue
        source = document.resolve(source_ref)
        sequence_ref = source.find("SequenceSource/Sequence")
        if sequence_ref is not None:
            return sequence_ref.get("ObjectURef")
    return None


def resolve_nested_sequence(clip: TrackItem) -> Sequence | None:
    """The `Sequence` `clip` plays from, or `None` if it plays from media.

    Works even when the clip's project-panel item has been removed - see
    the module docstring - which `clip.project_item.is_sequence` alone
    would miss.
    """
    uid = _master_sequence_uid(clip)
    if uid is None:
        return None
    project = clip.track.sequence.project
    for sequence in project.sequences:
        if sequence.sequence_id == uid:
            return sequence
    return None
