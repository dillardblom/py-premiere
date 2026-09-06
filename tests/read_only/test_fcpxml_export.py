"""FCPXML export.

Export has no byte-fidelity contract - it writes a different format - so
the checks here are structural: the document parses, every time is an exact
rational (Premiere ticks divide cleanly into seconds), every clip sits
inside the asset it reads from, and no clip is silently dropped.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from helpers import SAMPLES_DIR, each_sample

import py_premiere
from py_premiere.export import export_fcpxml
from py_premiere.export.fcpxml import _Resources, _build_spine
from py_premiere.models.nested_sequence import resolve_nested_sequence
from py_premiere.models.time import TICKS_PER_SECOND

MINIMAL = SAMPLES_DIR / "models" / "minimal"


def _media_clips_reachable(sequence, _visited_nested=None):
    """Every media-backed clip in `sequence`'s own tracks, plus one visit
    per DISTINCT nested sequence it references - however many times the
    same nested sequence is cut in (an ordinary trailer-editing pattern),
    matching `_Resources.add_nested_sequence`'s dedup-by-identity."""
    if _visited_nested is None:
        _visited_nested = set()
    clips = []
    for track in sequence.video_tracks + sequence.audio_tracks:
        for clip in track.clips:
            if clip.project_item is not None and clip.project_item.media_path:
                clips.append(clip)
                continue
            nested = resolve_nested_sequence(clip)
            if nested is not None and nested.sequence_id not in _visited_nested:
                _visited_nested.add(nested.sequence_id)
                clips.extend(_media_clips_reachable(nested, _visited_nested))
    return clips


def _rational(value: str) -> Fraction:
    assert value.endswith("s")
    body = value[:-1]
    if "/" in body:
        numerator, denominator = body.split("/")
        return Fraction(int(numerator), int(denominator))
    return Fraction(int(body))


def test_exports_a_sequence(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    target = export_fcpxml(application.project, tmp_path / "seq.fcpxml")
    root = ET.fromstring(target.read_bytes())

    assert root.tag == "fcpxml"
    fmt = root.find("resources/format")
    # 29.97 stays exact rather than becoming 0.0333...
    assert _rational(fmt.get("frameDuration")) == Fraction(1001, 30000)
    assert (fmt.get("width"), fmt.get("height")) == ("64", "36")

    spine = root.find("library/event/project/sequence/spine")
    assert spine is not None
    names = [c.get("name") for c in spine.iter("asset-clip")]
    # The video clip is on the spine; the audio is a connected clip, and
    # neither is dropped.
    assert names == ["red_64x36.bmp", "tone_440_1s.wav"]
    audio = spine.find(".//asset-clip[@lane='-1']")
    assert audio is not None, "audio should be a connected clip on a negative lane"


def test_every_clip_fits_inside_its_asset(tmp_path) -> None:
    # A clip's start is an offset into its source, so start + duration must
    # not run past the asset's declared span - Premiere's stills sit inside
    # a 12-hour phantom source, which is what makes this worth asserting.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    target = export_fcpxml(application.project, tmp_path / "fits.fcpxml")
    root = ET.fromstring(target.read_bytes())
    spans = {
        asset.get("id"): _rational(asset.get("duration"))
        for asset in root.iter("asset")
    }
    clips = list(root.iter("asset-clip"))
    assert clips
    for clip in clips:
        used = _rational(clip.get("start")) + _rational(clip.get("duration"))
        assert used <= spans[clip.get("ref")]


def test_media_paths_are_file_urls(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    target = export_fcpxml(application.project, tmp_path / "urls.fcpxml")
    root = ET.fromstring(target.read_bytes())
    sources = [rep.get("src") for rep in root.iter("media-rep")]
    assert sources
    assert all(src.startswith("file:///") for src in sources)


def test_project_without_a_sequence_raises(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "01_empty.prproj")
    with pytest.raises(ValueError):
        export_fcpxml(application.project, tmp_path / "empty.fcpxml")


@each_sample
def test_every_sample_exports_or_says_why(path, tmp_path) -> None:
    # Export must never produce a malformed document or lose a clip without
    # saying so: the only tolerated failures are the explicit ones.
    application = py_premiere.parse(path)
    if not application.project.sequences:
        pytest.skip("no sequence")
    for index, sequence in enumerate(application.project.sequences):
        try:
            target = export_fcpxml(
                application.project, tmp_path / f"{index}.fcpxml", sequence
            )
        except (NotImplementedError, ValueError):
            continue
        root = ET.fromstring(target.read_bytes())

        # Every clip backed by a media file has to reach the output; a clip
        # that silently vanishes is the failure this test exists to catch.
        # A nested sequence is flattened into its own <media> resource
        # (once per distinct sequence, however many times it is used - see
        # _Resources.add_nested_sequence), so its own media-backed clips
        # count too, exactly once each.
        assert len(list(root.iter("asset-clip"))) == len(_media_clips_reachable(sequence))

        # And every one of them has to resolve to an asset that declares the
        # stream it is being used for, or an importer drops it.
        assets = {asset.get("id"): asset for asset in root.iter("asset")}
        for clip_element in root.iter("asset-clip"):
            asset = assets.get(clip_element.get("ref"))
            assert asset is not None, clip_element.get("ref")
            lane = int(clip_element.get("lane") or 0)
            declared = "hasAudio" if lane < 0 else "hasVideo"
            assert asset.get(declared) == "1", (asset.get("id"), declared)


def _time(seconds: int) -> SimpleNamespace:
    ticks = seconds * TICKS_PER_SECOND
    return SimpleNamespace(ticks=ticks, seconds=seconds)


def _clip(
    name: str, start: int, end: int, *, media_path: Path | None = None, in_point: int = 0
) -> SimpleNamespace:
    """`start`/`end`/`in_point` are whole seconds, for readable test values."""
    project_item = (
        None if media_path is None else SimpleNamespace(media_path=media_path, name=name)
    )
    return SimpleNamespace(
        name=name,
        start=_time(start),
        end=_time(end),
        in_point=_time(in_point),
        duration=_time(end - start),
        project_item=project_item,
        # No <MasterClip> child, so resolve_nested_sequence's own
        # `.find("MasterClip")` comes back None - this fake clip is never a
        # nested-sequence reference.
        _subclip_element=ET.Element("Clip"),
    )


def _sequence(video_tracks: list, audio_tracks: list, end_seconds: int) -> SimpleNamespace:
    tracks = [SimpleNamespace(clips=clips) for clips in video_tracks]
    audio = [SimpleNamespace(clips=clips) for clips in audio_tracks]
    return SimpleNamespace(video_tracks=tracks, audio_tracks=audio, end=_time(end_seconds))


def test_title_or_nested_sequence_reserves_a_spine_slot_for_connected_clips() -> None:
    # A title card (like a nested sequence, an adjustment layer, ...) has no
    # media file, so `add_asset` cannot mint it a real `<asset-clip>`. It
    # must still occupy its span on the spine - real footage in production
    # archives routinely puts a logo/watermark overlay on V2 starting partway
    # through a V1 title, and that overlay needs somewhere to attach.
    intro = _clip("Intro.mp4", 0, 10, media_path=Path("intro.mp4"))
    title = _clip("Title Card", 10, 20)  # no media_path -> no asset
    overlay = _clip("Logo.png", 15, 20, media_path=Path("logo.png"))
    sequence = _sequence([[intro, title], [overlay]], [], end_seconds=20)

    spine = _build_spine(sequence, _Resources(), format_id="r1")

    title_gap = next(g for g in spine.findall("gap") if g.get("name") == "Title Card")
    assert _rational(title_gap.get("offset")) == Fraction(10)
    assert _rational(title_gap.get("duration")) == Fraction(10)

    attached = title_gap.find("asset-clip")
    assert attached is not None, (
        "connected clip must attach to the title's reserved slot, not raise"
    )
    assert attached.get("name") == "Logo.png"


def test_connected_clip_can_attach_during_a_deliberate_empty_gap() -> None:
    # A few empty frames between two clips (e.g. an extended fade to black)
    # is real, intentional content spacing - not "the sequence is done" - so
    # a connected clip starting inside it must still find a spine element.
    first = _clip("A.mp4", 0, 10, media_path=Path("a.mp4"))
    second = _clip("B.mp4", 15, 25, media_path=Path("b.mp4"))
    overlay = _clip("Watermark.png", 12, 15, media_path=Path("wm.png"))
    sequence = _sequence([[first, second], [overlay]], [], end_seconds=25)

    spine = _build_spine(sequence, _Resources(), format_id="r1")

    gap = spine.find("gap")
    assert gap is not None and gap.get("name") == "Gap"
    assert _rational(gap.get("offset")) == Fraction(10)
    assert _rational(gap.get("duration")) == Fraction(5)

    attached = gap.find("asset-clip")
    assert attached is not None, "overlay during a deliberate gap must not be dropped"
    assert attached.get("name") == "Watermark.png"


def test_nested_sequence_becomes_a_ref_clip_over_its_own_media_resource(tmp_path) -> None:
    # 66_eg_text's "Seq B" cuts in "Seq A" (video AND audio track items,
    # the same A/V pairing a regular media clip gets) plus a Graphic
    # overlay with no media of its own.
    application = py_premiere.parse(MINIMAL / "66_eg_text.prproj")
    target = export_fcpxml(application.project, tmp_path / "seq_b.fcpxml", application.project.sequences["Seq B"])
    root = ET.fromstring(target.read_bytes())

    media = root.find("resources/media")
    assert media is not None and media.get("name") == "Seq A"
    nested_spine = media.find("sequence/spine")
    assert nested_spine is not None
    # Seq A's own two clips (video + audio) reached the nested resource.
    assert len(list(nested_spine.iter("asset-clip"))) == 2

    top_spine = root.find("library/event/project/sequence/spine")
    primary_ref = top_spine.find("ref-clip")
    assert primary_ref is not None
    assert primary_ref.get("ref") == media.get("id")
    assert primary_ref.get("name") == "Seq A"
    # Seq A's audio track item is a connected clip on the same nested
    # sequence, hanging off the primary ref-clip exactly like a regular
    # A/V asset's audio half hangs off its video asset-clip.
    connected_ref = primary_ref.find("ref-clip")
    assert connected_ref is not None
    assert connected_ref.get("ref") == media.get("id")
    assert connected_ref.get("lane") == "-1"


def test_nested_sequence_resource_is_shared_across_references() -> None:
    # A trailer that cuts the same source sequence in twenty times over
    # (an ordinary trailer-editing pattern) must get ONE <media> resource,
    # not twenty copies of the same nested spine.
    application = py_premiere.parse(MINIMAL / "66_eg_text.prproj")
    seq_a = application.project.sequences["Seq A"]
    resources = _Resources()

    first = resources.add_nested_sequence(seq_a)
    second = resources.add_nested_sequence(seq_a)

    assert first == second
    assert len(resources.element.findall("media")) == 1


def test_nested_sequence_cycle_raises_instead_of_recursing_forever(monkeypatch) -> None:
    application = py_premiere.parse(MINIMAL / "66_eg_text.prproj")
    seq_a = application.project.sequences["Seq A"]
    clip = seq_a.video_tracks[0].clips[0]

    # Force the fixture's own footage clip to look like it nests seq_a
    # into itself - not a shape Premiere's UI can create, but exactly what
    # the guard exists to catch if it somehow occurred.
    monkeypatch.setattr(
        "py_premiere.export.fcpxml.resolve_nested_sequence",
        lambda c: seq_a if c is clip else None,
    )

    with pytest.raises(NotImplementedError, match="nested into itself"):
        _Resources().add_nested_sequence(seq_a)
