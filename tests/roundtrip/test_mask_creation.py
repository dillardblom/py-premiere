"""Mask creation against the 26_effect_mask fixture."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.xml.mutations import remove_child

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _normalized(element: ET.Element) -> str:
    # ObjectIDs reallocate on re-creation, and the OUTER tail is document
    # position (mid-table vs appended), not object identity; everything
    # else must reproduce Premiere's serialization exactly, internal
    # whitespace included.
    text = ET.tostring(element, encoding="unicode").rstrip("\n\t")
    return re.sub(r'(Object(?:ID|Ref))="\d+"', r'\1="N"', text)


def _masked_clip(
    application: py_premiere.models.Application,
) -> py_premiere.models.TrackItem:
    for sequence in application.project.sequences:
        for clip in sequence.clips:
            if clip.selection_components:
                return clip
    raise AssertionError("no clip-level mask in the project")


def test_recreating_the_clip_mask_matches_premieres_own(tmp_path) -> None:
    # Strip Premiere's own clip-role mask (chain + component + 27 params),
    # re-create it with py, and every element must serialize identically
    # (ObjectIDs aside) - full payloads included, since the stripped mask
    # was the document's payload carrier.
    application = py_premiere.parse(MINIMAL / "26_effect_mask.prproj")
    document = application.project._document
    clip = _masked_clip(application)

    chain_ref = clip._element.find("SelectionComponents")
    chain = document.resolve(chain_ref)
    mask = document.resolve(chain.find("ComponentChain/Components/Component"))
    params = [
        document.resolve(reference)
        for reference in mask.find("Component").findall("Params/Param")
    ]
    expected_chain = _normalized(chain)
    expected_mask = _normalized(mask)
    expected_params = [_normalized(param) for param in params]

    for element in [chain, mask, *params]:
        document.remove_object(element)
    remove_child(clip._element, chain_ref)
    clip._selection_components.clear()

    created = clip.add_mask()
    new_chain = document.resolve(clip._element.find("SelectionComponents"))
    assert _normalized(new_chain) == expected_chain
    assert _normalized(created._element) == expected_mask
    assert [
        _normalized(param._element) for param in created.properties
    ] == expected_params

    target = tmp_path / "reclipmask.prproj"
    application.project.save(target)
    fresh_clip = _masked_clip(parse_project_fresh(target))
    fresh_mask = fresh_clip.selection_components[0]
    assert fresh_mask.match_name == "AE.ADBE AEMask2"
    assert len(fresh_mask.properties) == 27
    # A shape mask stores an EMPTY path payload (geometry lives in the
    # Type/Scale/Rotation params).
    assert fresh_mask["Path"].path == []


def test_effect_mask_creation_round_trips(tmp_path) -> None:
    # 61_tint's Tint effect has no mask: add one, then read it back and
    # drive its geometry through the standard param setters.
    application = py_premiere.parse(MINIMAL / "61_tint.prproj")
    tint = next(
        clip.components["Tint"]
        for sequence in application.project.sequences
        for clip in sequence.clips
        if "Tint" in clip.components
    )
    mask = tint.add_mask()
    mask["Feather"].value = 30
    mask["Position"].value = [0.25, 0.75]

    target = tmp_path / "effectmask.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_tint = next(
        clip.components["Tint"]
        for sequence in fresh.project.sequences
        for clip in sequence.clips
        if "Tint" in clip.components
    )
    fresh_mask = fresh_tint.sub_components[0]
    assert fresh_mask.match_name == "AE.ADBE AEMask2"
    assert len(fresh_mask.properties) == 27
    assert fresh_mask["Feather"].value == 30.0
    assert fresh_mask["Position"].value == [0.25, 0.75]


def test_second_effect_mask_numbers_like_premiere(tmp_path) -> None:
    # 76_two_masks: the second mask takes InstanceName 02 and stamps the
    # effect's NextComponentNumber counter with 2.
    application = py_premiere.parse(MINIMAL / "26_effect_mask.prproj")
    clip = _masked_clip(application)
    blur = next(c for c in clip.components if c.sub_components)
    created = blur.add_mask()
    assert created._element.findtext("Component/InstanceName") == "02"
    counter = blur._element.findtext(
        "Component/Node/Properties/BE.VideoFilterComponent.NextComponentNumber"
    )
    assert counter == "2"

    target = tmp_path / "secondeffectmask.prproj"
    application.project.save(target)
    fresh_clip = _masked_clip(parse_project_fresh(target))
    fresh_blur = next(c for c in fresh_clip.components if c.sub_components)
    names = [
        mask._element.findtext("Component/InstanceName")
        for mask in fresh_blur.sub_components
    ]
    assert names == ["01", "02"]
    assert len(fresh_blur.sub_components[1].properties) == 27


def test_second_clip_mask_numbers_like_premiere(tmp_path) -> None:
    # 76_two_masks: further clip masks hang off the intrinsic holder as
    # effect-role sub-components (InstanceName restarts at 01) and the
    # holder's counter goes 2 -> 3.
    application = py_premiere.parse(MINIMAL / "26_effect_mask.prproj")
    document = application.project._document
    clip = _masked_clip(application)
    created = clip.add_mask()
    assert created._element.findtext("Component/InstanceName") == "01"
    holder = document.resolve(
        document.resolve(clip._element.find("SelectionComponents")).find(
            "ComponentChain/Components/Component"
        )
    )
    counter = holder.findtext(
        "Component/Node/Properties/BE.VideoFilterComponent.NextComponentNumber"
    )
    assert counter == "3"

    target = tmp_path / "secondclipmask.prproj"
    application.project.save(target)
    fresh_clip = _masked_clip(parse_project_fresh(target))
    fresh_holder = fresh_clip.selection_components[0]
    assert len(fresh_clip.selection_components) == 1
    assert len(fresh_holder.sub_components) == 1
    fresh_mask = fresh_holder.sub_components[0]
    assert fresh_mask.match_name == "AE.ADBE AEMask2"
    assert len(fresh_mask.properties) == 27
