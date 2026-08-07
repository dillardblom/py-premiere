"""FCPXML export.

Export has no byte-fidelity contract - it writes a different format - so
the checks here are structural: the document parses, every time is an exact
rational (Premiere ticks divide cleanly into seconds), every clip sits
inside the asset it reads from, and no clip is silently dropped.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction

import pytest
from helpers import SAMPLES_DIR, each_sample

import py_premiere
from py_premiere.export import export_fcpxml

MINIMAL = SAMPLES_DIR / "models" / "minimal"


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
        with_media = [
            clip
            for track in sequence.video_tracks + sequence.audio_tracks
            for clip in track.clips
            if clip.project_item is not None and clip.project_item.media_path
        ]
        assert len(list(root.iter("asset-clip"))) == len(with_media)

        # And every one of them has to resolve to an asset that declares the
        # stream it is being used for, or an importer drops it.
        assets = {asset.get("id"): asset for asset in root.iter("asset")}
        for clip_element in root.iter("asset-clip"):
            asset = assets.get(clip_element.get("ref"))
            assert asset is not None, clip_element.get("ref")
            lane = int(clip_element.get("lane") or 0)
            declared = "hasAudio" if lane < 0 else "hasVideo"
            assert asset.get(declared) == "1", (asset.get("id"), declared)
