"""Project.add_sequence builds the graph instead of cloning a template.

The parity evidence is `samples/refs/skeleton/py_seq_*_resave.prproj`:
Premiere opened a sequence this code built and saved it back with the
`Sequence`, `Track` and clip objects unchanged - the only difference being
the `MasterClipChangeVersion` counter it bumps on every save, plus the
project-level tree it regenerates for any skeleton.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models.sequence_builder import FORMATS, build_sequence

SKELETON = SAMPLES_DIR / "refs" / "skeleton"
#: What Premiere writes for a new sequence.
OBJECT_COUNT = 62


def test_fragment_has_every_object_premiere_writes() -> None:
    # Premiere regenerates NOTHING in a sequence - not even the 5 meters it
    # will happily open without - so all 62 have to be emitted.
    fragment = build_sequence()
    assert len(list(fragment)) == OBJECT_COUNT
    tags = [child.tag for child in fragment]
    assert tags.count("VideoClipTrack") == 3
    assert tags.count("AudioClipTrack") == 4
    assert tags.count("AudioFader") == 5  # one per audio track plus the master
    assert tags.count("AudioMeter") == 5
    assert tags.count("AudioComponentParam") == 14
    assert tags.count("StereoToStereoPanProcessor") == 4


def test_mono_discrete_is_a_different_graph() -> None:
    # Not just a bigger one: the panner class changes, the master clip
    # carries the 32-channel bus, and there is one serializer per track.
    tags = [child.tag for child in build_sequence("Seq01", "broadcast4mono")]
    assert tags.count("MonoTo16ChannelPanProcessor") == 4
    assert tags.count("StereoToStereoPanProcessor") == 0
    assert tags.count("SecondaryContent") == 32
    assert tags.count("ClipChannelSerializer") == 4
    eight = [child.tag for child in build_sequence("Seq01", "broadcast8mono")]
    assert eight.count("AudioClipTrack") == 8
    assert eight.count("MonoTo16ChannelPanProcessor") == 8
    assert eight.count("ClipChannelSerializer") == 8
    # The bus stays 32 channels however many tracks feed it.
    assert eight.count("SecondaryContent") == 32


def test_only_a_non_default_colour_space_gets_the_working_fields() -> None:
    # One profile name drives all three colour fields on the video track
    # group, and BT.709 writes only the output one.
    sdr = ET.tostring(build_sequence("Seq01", "2160p2997"), encoding="unicode")
    assert "WorkingColorSpace" not in sdr
    assert sdr.count("BT.709 RGB Full") == 1

    hdr = ET.tostring(build_sequence("Seq01", "2160p2997hdr"), encoding="unicode")
    assert "BT.709" not in hdr
    assert hdr.count("BT.2100 HLG RGB Full") == 3
    assert "<WorkingColorSpaceConfiguration>" in hdr
    # HDR previews in ProRes 422 HQ ('apch') rather than the 422 LT everything
    # else uses.
    assert "<MZ.Sequence.PreviewRenderingPresetCodec>1634755432<" in hdr


def test_a_preset_can_author_the_audio_track_height() -> None:
    # `mExpandedHeight` in the .sqpreset, which the 8-mono one sets to 25 so
    # eight tracks fit. Asymmetric on purpose: that preset asks for 25 on its
    # video tracks too and Premiere writes 41 for those regardless.
    def heights(preset: str, tag: str) -> list[str]:
        return [
            element.text or ""
            for child in build_sequence("Seq01", preset)
            if child.tag == tag
            for element in child.iter("TL.SQTrackExpandedHeight")
        ]

    assert heights("broadcast8mono", "AudioClipTrack") == ["25"] * 8
    assert heights("broadcast8mono", "VideoClipTrack") == ["41"] * 3
    assert heights("broadcast4mono", "AudioClipTrack") == ["41"] * 4


def test_every_reference_resolves_inside_the_fragment() -> None:
    fragment = build_sequence()
    ids = {child.get("ObjectID") for child in fragment if child.get("ObjectID")}
    uids = {child.get("ObjectUID") for child in fragment if child.get("ObjectUID")}
    for element in fragment.iter():
        reference = element.get("ObjectRef")
        if reference is not None:
            assert reference in ids, f"{element.tag} -> {reference}"
        reference = element.get("ObjectURef")
        if reference is not None:
            assert reference in uids, f"{element.tag} -> {reference}"


@pytest.mark.parametrize("preset", sorted(FORMATS))
def test_preset_values_land_where_premiere_puts_them(preset: str) -> None:
    fmt = FORMATS[preset]
    fragment = build_sequence("Seq01", preset)
    xml = ET.tostring(fragment, encoding="unicode")
    assert f"<FrameRect>0,0,{fmt.width},{fmt.height}</FrameRect>" in xml
    assert f"<FrameRate>{fmt.frame_rate}</FrameRate>" in xml
    assert f"<MZ.Sequence.VideoTimeDisplayFormat>{fmt.time_display}<" in xml
    # A virgin work area runs to 60 seconds floored to a whole frame.
    expected = 60 * 254016000000 // fmt.frame_rate * fmt.frame_rate
    assert f"<MZ.WorkOutPoint>{expected}</MZ.WorkOutPoint>" in xml


def test_identifiers_are_fresh_each_time() -> None:
    first = ET.tostring(build_sequence(), encoding="unicode")
    second = ET.tostring(build_sequence(), encoding="unicode")
    guid = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    # The class identifiers are shared; the minted ones must not be.
    assert set(guid.findall(first)) != set(guid.findall(second))


@pytest.mark.parametrize("preset", sorted(FORMATS))
def test_add_sequence_produces_a_usable_sequence(preset: str, tmp_path) -> None:
    application = py_premiere.new()
    sequence = application.project.add_sequence("Built", preset=preset)
    fmt = FORMATS[preset]
    assert sequence.name == "Built"
    assert sequence.frame_size == (fmt.width, fmt.height)
    assert sequence.timebase == fmt.frame_rate
    assert len(sequence.video_tracks) == 3
    assert len(sequence.audio_tracks) == fmt.audio_tracks
    # A mono-discrete preset gives each track its own channel.
    assert sequence.audio_channel_count == (
        fmt.audio_tracks if fmt.mono_discrete else 2
    )

    target = tmp_path / "built.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    reparsed = fresh.project.sequences[0]
    assert reparsed.name == "Built"
    assert reparsed.frame_size == (fmt.width, fmt.height)
    assert [item.name for item in fresh.project.root_item.children] == ["Built"]


@pytest.mark.parametrize("count", [1, 5, 8])
def test_video_track_count_is_overridable(count: int, tmp_path) -> None:
    # No preset Adobe ships varies this - all 10 ask for 3 - so the override
    # is the only way to reach another count. Checked through a save, since
    # a forgiving reader could report the right count from wrong text.
    application = py_premiere.new()
    application.project.add_sequence("Built", video_tracks=count)
    target = tmp_path / "tracks.prproj"
    application.project.save(target)

    sequence = parse_project_fresh(target).project.sequences[0]
    assert len(sequence.video_tracks) == count
    assert len(sequence.audio_tracks) == 4  # untouched by the override


def test_video_track_count_is_validated() -> None:
    application = py_premiere.new()
    with pytest.raises(ValueError):
        application.project.add_sequence("Nope", video_tracks=0)
    with pytest.raises(TypeError):
        application.project.add_sequence("Nope", video_tracks="3")


def test_two_sequences_do_not_collide(tmp_path) -> None:
    application = py_premiere.new()
    application.project.add_sequence("First")
    application.project.add_sequence("Second", preset="1080p2997")
    target = tmp_path / "two.prproj"
    application.project.save(target)

    fresh = parse_project_fresh(target)
    assert [s.name for s in fresh.project.sequences] == ["First", "Second"]
    assert fresh.project.sequences[0].timebase != fresh.project.sequences[1].timebase
    assert len({s.sequence_id for s in fresh.project.sequences}) == 2


def test_unknown_preset_is_refused() -> None:
    application = py_premiere.new()
    with pytest.raises(ValueError, match="unknown preset"):
        application.project.add_sequence("Nope", preset="4k60")


def test_premiere_resaves_a_built_sequence_unchanged() -> None:
    # The recorded verdict, scoped to the sequence: Premiere opened a project
    # this builder wrote and left its objects alone.
    built = SKELETON / "py_seq_1080p2997.prproj"
    resave = SKELETON / "py_seq_1080p2997_resave.prproj"
    if not built.exists() or not resave.exists():
        pytest.skip("local-only reference (Premiere resave of a py-built sequence)")
    before = py_premiere.parse(built).project.sequences[0]
    after = py_premiere.parse(resave).project.sequences[0]
    assert after.name == before.name
    assert after.frame_size == before.frame_size
    assert after.timebase == before.timebase
    assert len(after.video_tracks) == len(before.video_tracks) == 3
    assert len(after.audio_tracks) == len(before.audio_tracks) == 4
    assert after.audio_channel_count == before.audio_channel_count
