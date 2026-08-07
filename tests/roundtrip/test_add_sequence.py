"""Project.add_sequence: the from-scratch sequence template."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Time
from py_premiere.models.sequence_builder import FORMATS

MINIMAL = SAMPLES_DIR / "models" / "minimal"
ASSETS = SAMPLES_DIR / "models" / "assets"


def test_add_sequence_round_trips(tmp_path) -> None:
    # The template is Premiere's own createSequence graph (62 objects,
    # 1080p 23.976, 3V + 3A + master); pr-compare vs Premiere's reference
    # shows 0 objects only-in-either with only the fresh UIDs differing.
    application = py_premiere.parse(MINIMAL / "01_empty.prproj")
    sequence = application.project.add_sequence("My Timeline")
    assert sequence.name == "My Timeline"
    assert sequence.frame_size == (1920, 1080)
    assert len(sequence.video_tracks) == 3

    target = tmp_path / "seq.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_seq = fresh.project.sequences[0]
    assert fresh_seq.name == "My Timeline"
    assert fresh_seq.timebase == 10594584000
    panel = fresh.project.root_item.children[0]
    assert panel.name == "My Timeline"
    assert panel.is_sequence is True
    assert fresh_seq.project_item is not None


def test_two_sequences_get_distinct_identities(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "01_empty.prproj")
    first = application.project.add_sequence("A")
    second = application.project.add_sequence("B")
    assert first.sequence_id != second.sequence_id
    target = tmp_path / "two.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert [s.name for s in fresh.project.sequences] == ["A", "B"]


def test_full_from_scratch_pipeline(tmp_path) -> None:
    # new() -> add_sequence -> import_files -> add_clip -> add_marker: an
    # entire project built without Premiere.
    application = py_premiere.new()
    sequence = application.project.add_sequence("Built by py")
    items = application.project.import_files(
        [ASSETS / "bars_48x27.avi", ASSETS / "tone_880_hp5.wav"]
    )
    sequence.video_tracks[0].add_clip(items[0])
    sequence.audio_tracks[0].add_clip(items[1])
    sequence.add_marker("from scratch", Time(0))

    target = tmp_path / "pipeline.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    fresh_seq = fresh.project.sequences[0]
    assert [c.name for c in fresh_seq.video_tracks[0].clips] == ["bars_48x27.avi"]
    assert [c.name for c in fresh_seq.audio_tracks[0].clips] == ["tone_880_hp5.wav"]
    assert [m.name for m in fresh_seq.markers] == ["from scratch"]


def test_add_sequence_preset(tmp_path) -> None:
    # The 29.97 preset differs from the default in frame rate (touching the
    # track groups + settings); pr-compare vs Premiere's own
    # createSequenceWithPresetPath is 0 objects only-in-either.
    application = py_premiere.parse(MINIMAL / "01_empty.prproj")
    assert "1080p2997" in application.project.sequence_presets()
    sequence = application.project.add_sequence("Broadcast", preset="1080p2997")
    assert sequence.timebase == 8475667200
    assert sequence.frame_size == (1920, 1080)
    target = tmp_path / "preset.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert fresh.project.sequences[0].timebase == 8475667200


#: The measured value of every preset row, held INDEPENDENTLY of `FORMATS`
#: so the test cannot pass by agreeing with the table it is checking. Each
#: was read out of a sequence Premiere made from the matching `.sqpreset`
#: (`samples/refs/presets/`, which is local-only - hence the copy here):
#: frame rate, width, height, time display, audio tracks, video tracks,
#: preview format, preview codec, colour space, linear compositing,
#: mono-discrete.
_MEASURED = {
    "1080p23976": (
        10594584000,
        1920,
        1080,
        110,
        4,
        3,
        "fc3cd4d9-d839-8259-9276-05c5000000ea",
        "apcs",
        "BT.709 RGB Full",
        True,
        False,
    ),
    "1080p25": (
        10160640000,
        1920,
        1080,
        101,
        4,
        3,
        "fc3cd4d9-d839-8259-9276-05c5000000ea",
        "apcs",
        "BT.709 RGB Full",
        True,
        False,
    ),
    "1080p2997": (
        8475667200,
        1920,
        1080,
        102,
        4,
        3,
        "fc3cd4d9-d839-8259-9276-05c5000000ea",
        "apcs",
        "BT.709 RGB Full",
        True,
        False,
    ),
    "1080p50": (
        5080320000,
        1920,
        1080,
        105,
        4,
        3,
        "fc3cd4d9-d839-8259-9276-05c5000000ea",
        "apcs",
        "BT.709 RGB Full",
        True,
        False,
    ),
    "1080p5994": (
        4237833600,
        1920,
        1080,
        106,
        4,
        3,
        "fc3cd4d9-d839-8259-9276-05c5000000ea",
        "apcs",
        "BT.709 RGB Full",
        True,
        False,
    ),
    "2160p23976": (
        10594584000,
        3840,
        2160,
        110,
        4,
        3,
        "41384a52-7e4a-3c48-e0ad-4939000000ea",
        "apcs",
        "BT.709 RGB Full",
        False,
        False,
    ),
    "2160p23976hdr": (
        10594584000,
        3840,
        2160,
        110,
        4,
        3,
        "4e32a57e-26be-deca-0bf7-4548000000ea",
        "apch",
        "BT.2100 HLG RGB Full",
        False,
        False,
    ),
    "2160p25": (
        10160640000,
        3840,
        2160,
        101,
        4,
        3,
        "41384a52-7e4a-3c48-e0ad-4939000000ea",
        "apcs",
        "BT.709 RGB Full",
        False,
        False,
    ),
    "2160p25hdr": (
        10160640000,
        3840,
        2160,
        101,
        4,
        3,
        "4e32a57e-26be-deca-0bf7-4548000000ea",
        "apch",
        "BT.2100 HLG RGB Full",
        False,
        False,
    ),
    "2160p2997": (
        8475667200,
        3840,
        2160,
        102,
        4,
        3,
        "41384a52-7e4a-3c48-e0ad-4939000000ea",
        "apcs",
        "BT.709 RGB Full",
        False,
        False,
    ),
    "2160p2997hdr": (
        8475667200,
        3840,
        2160,
        102,
        4,
        3,
        "4e32a57e-26be-deca-0bf7-4548000000ea",
        "apch",
        "BT.2100 HLG RGB Full",
        False,
        False,
    ),
    "2160p50": (
        5080320000,
        3840,
        2160,
        105,
        4,
        3,
        "41384a52-7e4a-3c48-e0ad-4939000000ea",
        "apcs",
        "BT.709 RGB Full",
        False,
        False,
    ),
    "2160p50hdr": (
        5080320000,
        3840,
        2160,
        105,
        4,
        3,
        "4e32a57e-26be-deca-0bf7-4548000000ea",
        "apch",
        "BT.2100 HLG RGB Full",
        False,
        False,
    ),
    "2160p5994": (
        4237833600,
        3840,
        2160,
        106,
        4,
        3,
        "41384a52-7e4a-3c48-e0ad-4939000000ea",
        "apcs",
        "BT.709 RGB Full",
        False,
        False,
    ),
    "2160p5994hdr": (
        4233600000,
        3840,
        2160,
        108,
        4,
        3,
        "4e32a57e-26be-deca-0bf7-4548000000ea",
        "apch",
        "BT.2100 HLG RGB Full",
        False,
        False,
    ),
    "broadcast4mono": (
        10594584000,
        1920,
        1080,
        110,
        4,
        3,
        "fc3cd4d9-d839-8259-9276-05c5000000ea",
        "apcs",
        "BT.709 RGB Full",
        True,
        True,
    ),
    "broadcast8mono": (
        10594584000,
        1920,
        1080,
        110,
        8,
        3,
        "fc3cd4d9-d839-8259-9276-05c5000000ea",
        "apcs",
        "BT.709 RGB Full",
        True,
        True,
    ),
    "portrait1080p30": (
        8467200000,
        1080,
        1920,
        104,
        4,
        3,
        "01abac9c-c469-f667-c4a8-23a1000000ea",
        "apcs",
        "BT.709 RGB Full",
        True,
        False,
    ),
    "portrait1080p4x5": (
        8467200000,
        864,
        1080,
        104,
        4,
        3,
        "85cc5060-43fa-354a-99ff-02f0000000ea",
        "apcs",
        "BT.709 RGB Full",
        True,
        False,
    ),
    "square1080p30": (
        8467200000,
        1080,
        1080,
        104,
        4,
        3,
        "33cbb1f1-d0c5-3397-7a8d-a576000000ea",
        "apcs",
        "BT.709 RGB Full",
        True,
        False,
    ),
}


def test_the_measured_table_covers_every_preset() -> None:
    # A new preset row has to bring its measured values with it, or the
    # parametrized test below would silently skip it.
    assert sorted(_MEASURED) == sorted(FORMATS)


@pytest.mark.parametrize("preset", sorted(_MEASURED))
def test_every_preset_row_matches_what_premiere_measured(preset: str) -> None:
    # Compares `FORMATS` against the independent copy above rather than
    # against itself - the fields a preset actually decides, including the
    # four (preview format/codec, colour space, linear compositing) that
    # are the ONLY difference between an SDR row and its HDR twin.
    row = FORMATS[preset]
    assert (
        row.frame_rate,
        row.width,
        row.height,
        row.time_display,
        row.audio_tracks,
        row.video_tracks,
        row.preview_format,
        row.preview_codec,
        row.color_space,
        row.linear_compositing,
        row.mono_discrete,
    ) == _MEASURED[preset]


@pytest.mark.parametrize("preset", sorted(_MEASURED))
def test_every_preset_builds_and_round_trips(preset: str, tmp_path) -> None:
    # What the BUILDER makes of each row, checked against the measured
    # values rather than the table, so a wrong row fails here too.
    (rate, width, height, display, audio, video, *_) = _MEASURED[preset]
    application = py_premiere.parse(MINIMAL / "01_empty.prproj")
    sequence = application.project.add_sequence("Seq01", preset=preset)
    assert sequence.timebase == rate
    assert sequence.frame_size == (width, height)
    assert len(sequence.audio_tracks) == audio
    assert len(sequence.video_tracks) == video

    target = tmp_path / f"{preset}.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target).project.sequences[0]
    assert fresh.timebase == rate
    assert fresh.frame_size == (width, height)
    assert fresh.video_display_format == display
    assert len(fresh.audio_tracks) == audio


def test_the_preset_list_covers_the_built_in_families() -> None:
    presets = set(FORMATS)
    # Every rate of the HD and UHD sets, SDR and HDR, plus the social
    # sizes and the broadcast mono-discrete pair.
    assert {"1080p23976", "1080p25", "1080p2997", "1080p50", "1080p5994"} <= presets
    assert {
        "2160p23976",
        "2160p25",
        "2160p2997",
        "2160p50",
        "2160p5994",
    } <= presets
    assert {f"{key}hdr" for key in ("2160p23976", "2160p2997", "2160p50")} <= presets
    assert {"square1080p30", "portrait1080p30", "portrait1080p4x5"} <= presets


def test_add_sequence_rejects_unknown_preset() -> None:
    application = py_premiere.parse(MINIMAL / "01_empty.prproj")
    with pytest.raises(ValueError):
        application.project.add_sequence("Seq", preset="8k120fps")


def test_add_sequence_rejects_empty_name() -> None:
    application = py_premiere.parse(MINIMAL / "01_empty.prproj")
    with pytest.raises(ValueError):
        application.project.add_sequence("")
