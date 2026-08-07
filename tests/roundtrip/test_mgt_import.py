"""Motion Graphics template import, against Premiere's own import.

The fixture pair is marketplace content and cannot be committed, so these
skip unless both the `.mogrt` and the project Premiere's `importMGT`
produced from it are present locally (TODO section 4).
"""

from __future__ import annotations

import json
import zipfile

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models.mgt_builder import MEDIA_FOLDER, Template
from py_premiere.models.time import TICKS_PER_SECOND, Time

MOGRT = SAMPLES_DIR / "mogrt" / "513" / "credit-1.mogrt"
REFERENCE = SAMPLES_DIR / "refs" / "media" / "mgt.prproj"
BASE = SAMPLES_DIR / "models" / "minimal" / "06_api.prproj"

#: Applied per test rather than as a `pytestmark`: gating the whole module
#: took the checks that need NO local fixture out of CI with the rest, and
#: those are the only Motion Graphics coverage a fresh checkout gets.
needs_fixture = pytest.mark.skipif(
    not (MOGRT.exists() and REFERENCE.exists()),
    reason="the Motion Graphics template fixture is local-only",
)


@pytest.fixture(scope="module")
def template() -> Template:
    return Template(MOGRT)


@pytest.fixture(scope="module")
def reference():
    return py_premiere.parse(REFERENCE)


def _reference_master(application):
    bin_item = application.project.root_item.children[MEDIA_FOLDER]
    return bin_item.children[0]._master_element


def _payload(document, element, tag):
    child = element.find(tag)
    assert child is not None
    return document.payload(child)


def _capsule(application, master):
    document = application.project._document
    chain = document.resolve(master.find("BlueprintVideoComponentChain"))
    return document.resolve(chain.find("ComponentChain/Components/Component"))


def _params(application, component):
    document = application.project._document
    return [
        document.resolve(reference) for reference in component.find("Component/Params")
    ]


@needs_fixture
def test_template_reads_the_archive(template) -> None:
    with zipfile.ZipFile(MOGRT) as archive:
        definition = json.loads(archive.read("definition.json").decode("utf-8-sig"))
    assert template.capsule_id == definition["capsuleID"]
    assert template.name == "Credit Text 01"
    assert len(template.params) == 26
    assert not template.has_audio
    assert template.frame_size == (1920, 1080)
    assert template.frame_rate == 8467200000
    # 17.6 s at Premiere's tick rate, from the definition's `duration`.
    assert template.duration_ticks == 4470681600000
    assert template.time_display == 104


@needs_fixture
def test_derived_payloads_match_premieres(template, reference) -> None:
    # The two payloads py rebuilds from `definition.json` rather than
    # copying: the importer's own description of the media, and the
    # parameter set the component keeps privately.
    document = reference.project._document
    master = _reference_master(reference)
    source = document.resolve(
        document.resolve(master.find("Clips/Clip")).find("Clip/Source")
    )
    media = document.resolve(source.find("MediaSource/Media"))
    prefs = _payload(document, media, "ImporterPrefs")
    assert prefs.decode("utf-16-le") == template.importer_prefs

    component = _capsule(reference, master)
    private = _payload(document, component, "PremiereFilterPrivateData")
    assert private.decode("utf-16-le") == template.private_data


def _import(tmp_path):
    application = py_premiere.parse(BASE)
    # The graphic is copied next to the project, so import into a copy.
    target = tmp_path / "mgt.prproj"
    application.project.save(target)
    application = py_premiere.parse(target)
    placed = application.project.sequences["Seq A"].import_mgt(MOGRT)
    return application, placed


@needs_fixture
def test_import_writes_the_graphic_beside_the_project(tmp_path, template) -> None:
    application, _ = _import(tmp_path)
    copied = template.media_path(application.project.path.parent)
    assert copied.read_bytes() == template.graphic
    assert copied.parent.name == template.capsule_id


@needs_fixture
def test_is_mgt_identifies_the_imported_item(tmp_path, reference) -> None:
    # Premiere's own import and py's both flag the same way, and nothing
    # else in the project does.
    for application in (reference, _import(tmp_path)[0]):
        item = application.project.root_item.children[MEDIA_FOLDER].children[0]
        assert item.is_mgt
        others = [
            child
            for child in application.project.root_item.children
            if child.name != MEDIA_FOLDER
        ]
        assert others and not any(child.is_mgt for child in others)


@needs_fixture
def test_import_files_the_item_into_the_media_bin(tmp_path) -> None:
    application, _ = _import(tmp_path)
    bin_item = application.project.root_item.children[MEDIA_FOLDER]
    assert [child.name for child in bin_item.children] == ["Credit Text 01"]
    # A second import reuses the bin rather than adding a numbered twin.
    application.project.sequences["Seq A"].import_mgt(MOGRT)
    assert [item.name for item in application.project.root_item.children].count(
        MEDIA_FOLDER
    ) == 1
    assert len(bin_item.children) == 2


@needs_fixture
def test_a_second_import_overwrites_the_first(tmp_path) -> None:
    # `add_mgt` documents that it OVERWRITES whole clips it lands on. The
    # bin-reuse test above already runs a second import over the first, but
    # asserts only on the bin - so a `_clips_within` that returned nothing
    # would leave two stacked placements and still pass there.
    application, placed = _import(tmp_path)
    track = placed.track
    assert len(track.clips) == 1
    first = track.clips[0]._element.get("ObjectID")

    application.project.sequences["Seq A"].import_mgt(MOGRT)
    assert len(track.clips) == 1, "the covered placement was not removed"
    assert track.clips[0]._element.get("ObjectID") != first

    target = tmp_path / "overwritten.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert len(fresh.project.sequences["Seq A"].video_tracks[0].clips) == 1


@needs_fixture
def test_a_partly_covering_placement_is_refused(tmp_path) -> None:
    # The other half of the same contract: a span that would only partly
    # cover a clip needs a trim, which is not supported, so it must raise
    # rather than silently erase or overlap.
    application, placed = _import(tmp_path)
    half = Time(placed.duration.ticks // 2)
    with pytest.raises(ValueError, match="partly cover"):
        application.project.sequences["Seq A"].import_mgt(MOGRT, half)


@needs_fixture
def test_placement_matches_premieres(tmp_path, reference) -> None:
    application, placed = _import(tmp_path)
    expected = reference.project.sequences["Seq A"].video_tracks[0].clips[0]
    assert placed.start.ticks == expected.start.ticks
    assert placed.end.ticks == expected.end.ticks
    assert placed.name == expected.name
    identifier = (
        "ClipTrackItem/TrackItem/Node/Properties/BE.RushInspectorPanel.MogrtIdentifier"
    )
    assert placed._element.findtext(identifier) == expected._element.findtext(
        identifier
    )


def _source_durations(application, sequence_name):
    project = application.project
    uid = project.sequences[sequence_name].sequence_id
    out = {}
    for element in project._document.root:
        if not element.tag.endswith("SequenceSource"):
            continue
        node = element.find("SequenceSource/Sequence")
        if node is not None and node.get("ObjectURef") == uid:
            out[element.tag] = int(element.findtext("OriginalDuration") or 0)
    return out


@needs_fixture
def test_the_sequence_reports_its_new_length(tmp_path, reference) -> None:
    # The template outruns everything Seq A held, so the length the
    # sequence reports as a source has to grow - to exactly what Premiere
    # wrote importing the same template.
    application, _ = _import(tmp_path)
    assert _source_durations(application, "Seq A") == _source_durations(
        reference, "Seq A"
    )


@needs_fixture
def test_control_set_matches_premieres(tmp_path, reference) -> None:
    application, _ = _import(tmp_path)
    document = application.project._document
    built = _capsule(application, _reference_master(application))
    expected_document = reference.project._document
    expected = _capsule(reference, _reference_master(reference))

    assert built.findtext("MatchName") == "AE.ADBE Capsule"
    assert built.findtext("Component/DisplayName") == "Graphic Parameters"

    for param, wanted in zip(_params(application, built), _params(reference, expected)):
        assert param.tag == wanted.tag
        assert param.findtext("Name") == wanted.findtext("Name")
        assert param.findtext("ParameterID") == wanted.findtext("ParameterID")
        assert param.findtext("ParameterControlType") == wanted.findtext(
            "ParameterControlType"
        )
        assert param.findtext("StartKeyframe") == wanted.findtext("StartKeyframe")
        value = param.find("StartKeyframeValue")
        if value is None:
            assert wanted.find("StartKeyframeValue") is None
            continue
        assert document.payload(value) == expected_document.payload(
            wanted.find("StartKeyframeValue")
        )


@needs_fixture
def test_placement_carries_its_own_control_set(tmp_path) -> None:
    application, placed = _import(tmp_path)
    document = application.project._document
    master_component = _capsule(application, _reference_master(application))
    chain = document.resolve(
        placed._element.find("ClipTrackItem/ComponentOwner/Components")
    )
    placement_component = document.resolve(
        chain.find("ComponentChain/Components/Component")
    )
    assert placement_component is not master_component
    # Store-once: the copy references the master's payloads.
    for param in _params(application, placement_component):
        value = param.find("StartKeyframeValue")
        if value is not None:
            assert not (value.text or "").strip()
            assert document.payload(value) is not None
    assert [component.display_name for component in placed.components] == [
        "Graphic Parameters"
    ]


@needs_fixture
def test_import_round_trips(tmp_path) -> None:
    application, _ = _import(tmp_path)
    saved = tmp_path / "saved.prproj"
    application.project.save(saved)
    fresh = parse_project_fresh(saved)
    item = fresh.project.root_item.children[MEDIA_FOLDER].children["Credit Text 01"]
    component = _capsule(fresh, item._master_element)
    params = _params(fresh, component)
    assert len(params) == 26
    document = fresh.project._document
    text = document.payload(params[1].find("StartKeyframeValue"))
    assert "Rachel Green" in text.decode("utf-16-le")


@needs_fixture
def test_marking_an_imported_template_builds_the_collection(tmp_path) -> None:
    # py's own master carries no `MarkerOwner` - Premiere writes one on
    # every import, but a synthesized graph has no reason to - so the
    # first marker has to build it, between the bag and `Source`.
    application, _ = _import(tmp_path)
    item = application.project.root_item.children[MEDIA_FOLDER].children[0]
    core = item._own_clip_core()
    assert core.find("MarkerOwner") is None

    item.add_marker("cue", Time(TICKS_PER_SECOND), comments="on the template")
    tags = [child.tag for child in core]
    assert tags.index("MarkerOwner") == tags.index("Source") - 1

    saved = tmp_path / "marked.prproj"
    application.project.save(saved)
    fresh = parse_project_fresh(saved)
    marked = fresh.project.root_item.children[MEDIA_FOLDER].children[0]
    assert [marker.name for marker in marked.markers] == ["cue"]
    assert marked.markers[0].comments == "on the template"


@needs_fixture
def test_import_rejects_an_audio_track(tmp_path) -> None:
    application = py_premiere.parse(BASE)
    target = tmp_path / "mgt.prproj"
    application.project.save(target)
    application = py_premiere.parse(target)
    with pytest.raises(ValueError, match="video tracks"):
        application.project.sequences["Seq A"].audio_tracks[0].add_mgt(MOGRT)


def test_a_non_mogrt_file_is_refused_cleanly() -> None:
    # A .mogrt is a zip; pointing at anything else must read as that, not as
    # a zipfile error from inside the archive reader.
    application = py_premiere.parse(
        SAMPLES_DIR / "models" / "minimal" / "06_api.prproj"
    )
    with pytest.raises(ValueError, match="Motion Graphics template"):
        application.project.sequences[0].import_mgt(
            SAMPLES_DIR / "models" / "assets" / "red_64x36.bmp"
        )
