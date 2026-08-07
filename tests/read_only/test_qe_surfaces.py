"""Surfaces whose fixtures only the QE DOM could produce.

Neither ExtendScript nor UXP can write any of these, so every fixture here
came from `scripts/jsx/make_qe_fixtures*.jsx`.
"""

from __future__ import annotations

from helpers import SAMPLES_DIR

import py_premiere
from py_premiere.enums import (
    GeneratorType,
    ProjectItemType,
    TimeInterpolationType,
)

MINIMAL = SAMPLES_DIR / "models" / "minimal"
FRAME = 8475667200


def _seq_b(application: py_premiere.Application) -> py_premiere.Sequence:
    # QE edits whatever sequence is FRONTED, which for 06_api is Seq B.
    return next(s for s in application.project.sequences if s.name == "Seq B")


def _first_clip(fixture: str) -> py_premiere.TrackItem:
    application = py_premiere.parse(MINIMAL / fixture)
    return _seq_b(application).video_tracks[0].clips[0]


# --- generators ------------------------------------------------------------


def test_generator_items_identify_themselves() -> None:
    application = py_premiere.parse(MINIMAL / "34_generators.prproj")
    found = {
        item.name: (item.generator_id, item.generator_type)
        for item in application.project.root_item.children
        if item.generator_id is not None
    }
    assert found == {
        "Black Video": ("BLAK", GeneratorType.BLACK_VIDEO),
        "Color Matte": ("COLR", GeneratorType.COLOR_MATTE),
        "HD Bars and Tone": ("BARS", GeneratorType.BARS_AND_TONE),
        "Transparent Video": ("TRNV", GeneratorType.TRANSPARENT_VIDEO),
        "Universal Counting Leader": ("LEAD", GeneratorType.UNIVERSAL_COUNTING_LEADER),
    }


def test_generated_media_has_no_path() -> None:
    # The fourcc sits where the file path would be, so ExtendScript (and py)
    # report no media path at all for these.
    application = py_premiere.parse(MINIMAL / "34_generators.prproj")
    for item in application.project.root_item.children:
        if item.generator_type is not None:
            assert item.media_path is None


def test_real_media_is_not_a_generator() -> None:
    application = py_premiere.parse(MINIMAL / "34_generators.prproj")
    bmp = application.project.root_item.children[0]
    assert bmp.media_path is not None
    assert bmp.generator_id is None
    assert bmp.generator_type is None


def test_adjustment_layer_is_backed_by_black_video() -> None:
    application = py_premiere.parse(MINIMAL / "22_adjustment_layer.prproj")
    layers = [
        item
        for item in application.project.root_item.children
        if item.is_adjustment_layer
    ]
    assert len(layers) == 1
    assert layers[0].generator_type is GeneratorType.BLACK_VIDEO


# --- time interpolation ----------------------------------------------------


def test_interpolation_defaults_to_frame_sampling() -> None:
    # Premiere elides the field at frame sampling, and writing 0 through QE
    # removes it again.
    for fixture in ("06_api.prproj", "42_interp_sampling.prproj"):
        clip = _first_clip(fixture)
        assert clip.time_interpolation_type is TimeInterpolationType.FRAME_SAMPLING


def test_frame_blend_is_interpolation_type_one() -> None:
    # The legacy `setFrameBlend(true)` and `setTimeInterpolationType(1)` write
    # the same stored value, which is what makes the enum mapping certain.
    assert (
        _first_clip("40_frame_blend.prproj").time_interpolation_type
        is TimeInterpolationType.FRAME_BLENDING
    )
    assert (
        _first_clip("41_interp_blending.prproj").time_interpolation_type
        is TimeInterpolationType.FRAME_BLENDING
    )


def test_optical_flow_with_a_speed_change() -> None:
    clip = _first_clip("37_retime.prproj")
    assert clip.time_interpolation_type is TimeInterpolationType.OPTICAL_FLOW
    assert clip.speed == 0.5
    assert clip.is_speed_reversed is False


# --- transition parameters -------------------------------------------------


def test_wipe_transition_parameters() -> None:
    application = py_premiere.parse(MINIMAL / "39_transition_wipe.prproj")
    transitions = _seq_b(application).video_tracks[0].transitions
    assert len(transitions) == 1
    wipe = transitions[0]
    assert wipe.name == "Band Wipe"
    assert wipe.match_name == "ADBE Band Wipe"
    assert wipe.border_width == 20
    assert wipe.border_color == (255, 0, 0, 255)
    assert wipe.is_reversed is True
    assert wipe.anti_alias_quality == 2
    # Not set by the fixture - Band Wipe's own default, kept raw.
    assert wipe.direction == 10


def test_a_dissolve_has_no_wipe_parameters() -> None:
    application = py_premiere.parse(MINIMAL / "07_transitions.prproj")
    dissolve = application.project.sequences[0].video_tracks[0].transitions[0]
    assert dissolve.border_width == 0
    assert dissolve.border_color is None
    assert dissolve.is_reversed is False
    assert dissolve.direction == 0
    assert dissolve.anti_alias_quality == 0


# --- razor and added tracks ------------------------------------------------


def test_razor_splits_a_clip_into_two() -> None:
    # QE razored at 00:00:02:00 - 60 frames at 29.97, which is 2.002s.
    application = py_premiere.parse(MINIMAL / "35_razor.prproj")
    sequence = _seq_b(application)
    clips = sequence.video_tracks[0].clips
    assert len(clips) == 2
    assert clips[0].start.ticks == 0
    assert clips[0].end.ticks == 60 * FRAME
    assert clips[1].start.ticks == 60 * FRAME
    # Both halves still instance the same panel item.
    assert clips[0].project_item is not None
    assert clips[0].project_item.name == clips[1].project_item.name
    # The audio side was razored too.
    assert len(sequence.audio_tracks[0].clips) == 2


def test_added_tracks_are_read() -> None:
    application = py_premiere.parse(MINIMAL / "36_add_tracks.prproj")
    sequence = _seq_b(application)
    assert len(sequence.video_tracks) == 5
    assert len(sequence.audio_tracks) == 5
    # The two added tracks are empty and land after the originals.
    assert [track.index for track in sequence.video_tracks] == [0, 1, 2, 3, 4]
    assert all(track.clips == [] for track in sequence.video_tracks[1:])
    untouched = py_premiere.parse(MINIMAL / "06_api.prproj")
    assert len(_seq_b(untouched).video_tracks) == 3


def test_native_pixel_aspect_is_read_without_an_override() -> None:
    # HD bars are anamorphic: the media carries OriginalPAR 40,33 and no
    # override, which py used to report as square pixels.
    application = py_premiere.parse(MINIMAL / "34_generators.prproj")
    bars = next(
        item
        for item in application.project.root_item.children
        if item.generator_type is GeneratorType.BARS_AND_TONE
    )
    interpretation = bars.footage_interpretation
    assert interpretation is not None
    assert interpretation.pixel_aspect_ratio == 40 / 33
    # Square-pixel media stores no PAR at all.
    bmp = application.project.root_item.children[0]
    assert bmp.footage_interpretation is not None
    assert bmp.footage_interpretation.pixel_aspect_ratio == 1.0


# --- slip and slide --------------------------------------------------------


def _v1_times(fixture: str) -> list[tuple[int, int, int, int]]:
    application = py_premiere.parse(MINIMAL / fixture)
    return [
        (clip.start.ticks, clip.end.ticks, clip.in_point.ticks, clip.out_point.ticks)
        for clip in _seq_b(application).video_tracks[0].clips
    ]


def test_slip_moves_the_source_and_not_the_timeline() -> None:
    # QE slipped the first of the two razored clips by 10 frames. A slip moves
    # what the clip PLAYS without moving where it sits, so start/end must be
    # untouched while in/out shift - which is only visible if py reads the two
    # independently. The source here is a nested sequence with no handles
    # before zero, so the in point goes NEGATIVE and must survive as such.
    before = _v1_times("35_razor.prproj")
    after = _v1_times("43_slip.prproj")
    assert len(after) == 2
    assert (after[0][0], after[0][1]) == (before[0][0], before[0][1])
    assert after[0][2] == before[0][2] - 10 * FRAME
    assert after[0][3] == before[0][3] - 10 * FRAME
    assert after[0][2] < 0
    assert after[1] == before[1]


def test_slide_moves_the_cut_and_keeps_the_source() -> None:
    # Sliding the second clip by 10 frames moves the cut between the two: the
    # first clip grows, the second shifts later, and neither source moves.
    before = _v1_times("35_razor.prproj")
    after = _v1_times("44_slide.prproj")
    assert after[0][1] == before[0][1] + 10 * FRAME
    assert after[1][0] == before[1][0] + 10 * FRAME
    assert after[1][1] == before[1][1] + 10 * FRAME
    assert (after[1][2], after[1][3]) == (before[1][2], before[1][3])


# --- work area, playhead and sequence settings -----------------------------


def _seq_b_of(fixture: str) -> py_premiere.Sequence:
    return _seq_b(py_premiere.parse(MINIMAL / fixture))


def test_work_area_and_playhead() -> None:
    # setWorkInOutPoints("00:00:01:00", "00:00:03:00"),
    # setInOutPoints("00:00:00:10", "00:00:02:00"), setCTI("00:00:01:15").
    sequence = _seq_b_of("50_work_area.prproj")
    assert sequence.work_area_in.ticks == 30 * FRAME
    assert sequence.work_area_out.ticks == 90 * FRAME
    assert sequence.in_point.ticks == 10 * FRAME
    assert sequence.out_point.ticks == 60 * FRAME
    assert sequence.playhead.ticks == 45 * FRAME


def test_untouched_work_area_covers_everything() -> None:
    # A virgin sequence runs its work area to 60 seconds floored to a frame,
    # not to its own end.
    sequence = _seq_b_of("06_api.prproj")
    assert sequence.work_area_in.ticks == 0
    assert sequence.work_area_out.ticks > sequence.end.ticks
    timebase = sequence.timebase or 1
    assert sequence.work_area_out.ticks == 60 * 254016000000 // timebase * timebase
    assert sequence.playhead.ticks == 0


def test_preview_settings_read_non_default_values() -> None:
    # setPreviewFrameSize(32, 18), setUseMaxBitDepth(true),
    # setUseMaxRenderQuality(true) - the settings model had never been
    # exercised with anything but the defaults.
    settings = _seq_b_of("49_seq_settings.prproj").settings
    assert settings.preview_frame_size == (32, 18)
    assert settings.max_bit_depth is True
    assert settings.max_render_quality is True
    default = _seq_b_of("06_api.prproj").settings
    assert default.preview_frame_size == (64, 36)
    assert default.max_bit_depth is False
    assert default.max_render_quality is False


# --- move, roll and clip removal -------------------------------------------


def test_move_shifts_the_timeline_only() -> None:
    # move("10") slides the clip 10 frames later; its source is untouched.
    before = _v1_times("35_razor.prproj")
    after = _v1_times("45_move.prproj")
    assert after[1][0] == before[1][0] + 10 * FRAME
    assert after[1][1] == before[1][1] + 10 * FRAME
    assert after[1][2] == before[1][2]
    assert after[0] == before[0]


def test_roll_moves_the_cut_and_both_sources() -> None:
    # A roll differs from a slide: the neighbour's SOURCE moves with the cut,
    # so the pair keeps its overall length.
    before = _v1_times("35_razor.prproj")
    after = _v1_times("52_roll.prproj")
    assert after[0][1] == before[0][1] + 10 * FRAME
    assert after[1][0] == before[1][0] + 10 * FRAME
    assert after[1][2] == before[1][2] + 10 * FRAME
    assert after[1][1] == before[1][1]


def test_removing_a_clip_leaves_the_others_in_place() -> None:
    # QE `remove(true, true)` lifts the clip: the survivor does NOT ripple
    # back to the start.
    before = _v1_times("35_razor.prproj")
    after = _v1_times("53_remove_clip.prproj")
    assert len(after) == len(before) - 1
    assert after[0] == before[1]


# --- new panel item kinds --------------------------------------------------


def test_smart_bin_reads_as_a_named_bin() -> None:
    # A SmartBinProjectItem wraps a BinProjectItem, so without the
    # intermediate-class lookup it read as an unnamed CLIP.
    application = py_premiere.parse(MINIMAL / "48_smart_bin.prproj")
    bins = [
        item
        for item in application.project.root_item.children
        if item.type is ProjectItemType.BIN
    ]
    assert len(bins) == 1
    assert bins[0].name == "Reds"
    assert bins[0].children == []


def test_dynamic_link_item_reads_its_ae_project() -> None:
    application = py_premiere.parse(MINIMAL / "51_ae_comp.prproj")
    linked = [
        item
        for item in application.project.root_item.children
        if item.media_path is not None and item.media_path.suffix == ".aep"
    ]
    assert len(linked) == 1
    assert linked[0].name.endswith("comp_1920x1080.aep")
    assert linked[0].generator_type is None
