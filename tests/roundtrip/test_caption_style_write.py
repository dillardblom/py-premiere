"""Writing the named caption style slots."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models import Color
from py_premiere.models import caption as caption_payload

MINIMAL = SAMPLES_DIR / "models" / "minimal"

#: Every writable style property, with a value distinct from the corpus
#: defaults so a stale read cannot pass by accident.
STYLE = {
    "font_size": 66.0,
    "fill_color": Color(200, 100, 50),
    "stroke_color": Color(1, 2, 3),
    "stroke_width": 4.5,
    "tracking": 12.0,
    "leading": 34.0,
    "shadow_color": Color(7, 8, 9),
    "shadow_opacity": 55.0,
    "shadow_angle": 60.0,
    "shadow_distance": 5.0,
    "shadow_size": 6.0,
    "shadow_blur": 7.0,
    "background_color": Color(10, 20, 30),
    "background_opacity": 65.0,
    "background_size": 8.0,
    "background_corner_radius": 9.0,
}


def _captions(application: py_premiere.models.Application):
    return next(
        s.caption_tracks[0] for s in application.project.sequences if s.caption_tracks
    ).captions


def _flag_byte(payload: bytes, locate, slot: int):
    # The stored value of a table's ubyte enable flag, or None when absent.
    field = caption_payload._field_offset(payload, locate(payload), slot)
    return None if field is None else payload[field]


def test_stroke_and_background_writes_enable_their_groups(tmp_path) -> None:
    # The Appearance panel renders a group only while its enable flag - the
    # ubyte right after the group's colour - is 1. Premiere's own save
    # (82_caption_style_sweep) carries style[5] and doc[18]; a py write of
    # any stroke or background value has to raise them too, or the stored
    # values sit behind an unchecked checkbox. Width parity with 82: the
    # flag is packed as a single ubyte, not a padded word.
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = _captions(application)[0]
    caption.stroke_width = 4.5
    caption.background_opacity = 65.0
    target = tmp_path / "enabled.prproj"
    application.project.save(target)
    fresh = _captions(parse_project_fresh(target))[0]
    payload = fresh._payload()
    assert _flag_byte(payload, caption_payload._style_table, 5) == 1
    assert _flag_byte(payload, caption_payload._document_table, 18) == 1
    assert fresh.stroke_width == 4.5
    assert fresh.background_opacity == 65.0


def test_a_sub_word_add_composes_with_later_adds(tmp_path) -> None:
    # CAMPAIGN 6c's regression bar: a 1-byte flag add followed by any
    # other add must leave every existing slot readable. The historical
    # failure was indirect - once edits grew the buffer far enough, a run
    # vector's count shape-checked as a table soffset and the offset
    # walker dropped the subtree, so the NEXT splice severed the style
    # table (font_size fell back to 100) or a flag's `01` word read as a
    # bogus one-char text string.
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = _captions(application)[0]
    payload = caption._payload()

    style = caption_payload._style_table(payload)
    payload = caption_payload._add_table_field(payload, style, 5, b"\x01")
    # Width parity with Premiere's 82 packing: the flag is a ubyte, so the
    # object grows by exactly one declared byte.
    style = caption_payload._style_table(payload)
    vtable = caption_payload._valid_vtable(payload, style)
    (object_size,) = caption_payload._unpack("<H", payload, vtable + 2)
    field = caption_payload._field_offset(payload, style, 5)
    assert object_size == (field - style) + 1

    payload = caption_payload.write_style_color(payload, 2, Color(11, 22, 33))
    payload = caption_payload.write_style_float(payload, 8, 17.0)
    payload = caption_payload.write_block_float(payload, 34, 9.0)
    payload = caption_payload._write_table_flag(
        payload, caption_payload._document_table, 18
    )

    assert caption_payload.read_font_size(payload) == 48.0
    assert caption_payload.decode_caption_text(payload) == "Hello from py-premiere"
    assert caption_payload.read_font_family(payload) == "LucidaConsole"
    assert caption_payload.read_style_color(payload, 2) == Color(11, 22, 33)
    assert caption_payload.read_style_float(payload, 8) == 17.0
    assert caption_payload.read_block_float(payload, 34) == 9.0
    assert _flag_byte(payload, caption_payload._style_table, 5) == 1
    assert _flag_byte(payload, caption_payload._document_table, 18) == 1

    caption._write_payload(payload)
    target = tmp_path / "subword.prproj"
    application.project.save(target)
    fresh = _captions(parse_project_fresh(target))[0]
    assert fresh.font_size == 48.0
    assert fresh.text == "Hello from py-premiere"
    assert fresh.fill_color == Color(11, 22, 33)
    assert fresh.tracking == 17.0
    assert fresh.background_corner_radius == 9.0


def test_styling_an_unstyled_caption_round_trips(tmp_path) -> None:
    # 29's captions carry Premiere's defaults, so most of these slots are
    # ABSENT and have to be added to the FlatBuffer, not just patched.
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = _captions(application)[0]
    for name, value in STYLE.items():
        setattr(caption, name, value)
    for name, value in STYLE.items():
        assert getattr(caption, name) == value, name

    target = tmp_path / "styled.prproj"
    application.project.save(target)
    fresh = _captions(parse_project_fresh(target))
    for name, value in STYLE.items():
        assert getattr(fresh[0], name) == value, name
    # The text, family and the neighbouring caption are untouched.
    assert fresh[0].text == "Hello from py-premiere"
    assert fresh[0].font_family == "LucidaConsole"
    assert fresh[1].text == "Second caption line"
    assert fresh[1].tracking is None


def test_restyling_an_already_styled_caption(tmp_path) -> None:
    # 82's slots all exist, so these are in-place patches.
    application = py_premiere.parse(MINIMAL / "82_caption_style_sweep.prproj")
    caption = _captions(application)[0]
    caption.tracking = 99.0
    caption.fill_color = Color(3, 2, 1)
    caption.shadow_angle = 15.0
    target = tmp_path / "restyled.prproj"
    application.project.save(target)
    fresh = _captions(parse_project_fresh(target))[0]
    assert fresh.tracking == 99.0
    assert fresh.fill_color == Color(3, 2, 1)
    assert fresh.shadow_angle == 15.0
    # Untouched sentinels survive.
    assert fresh.stroke_color == Color(44, 55, 66)
    assert fresh.background_corner_radius == 44.0
    assert fresh.font_size == 75.0


def test_style_writes_compose_with_text_and_family(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = _captions(application)[0]
    caption.tracking = 5.0
    caption.text = "Restyled and retexted"
    caption.font_family = "Arial"
    caption.fill_color = Color(255, 0, 0)
    caption.font_size = 40.0
    target = tmp_path / "composed.prproj"
    application.project.save(target)
    fresh = _captions(parse_project_fresh(target))[0]
    assert fresh.text == "Restyled and retexted"
    assert fresh.font_family == "Arial"
    assert fresh.tracking == 5.0
    assert fresh.fill_color == Color(255, 0, 0)
    assert fresh.font_size == 40.0


def test_styling_a_py_created_caption(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    item = application.project.import_files(
        [SAMPLES_DIR / "models" / "assets" / "two_lines.srt"]
    )[0]
    track = application.project.sequences[0].create_caption_track(item)
    track.captions[0].fill_color = Color(12, 34, 56)
    track.captions[0].tracking = 8.0
    target = tmp_path / "imported_styled.prproj"
    application.project.save(target)
    fresh = _captions(parse_project_fresh(target))
    assert fresh[0].fill_color == Color(12, 34, 56)
    assert fresh[0].tracking == 8.0
    assert fresh[1].fill_color is None


def test_style_write_validation() -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = _captions(application)[0]
    with pytest.raises(TypeError):
        caption.tracking = "wide"
    with pytest.raises(TypeError):
        caption.fill_color = (255, 0, 0)
    with pytest.raises(ValueError):
        caption.fill_color = Color(300, 0, 0)


def test_colour_setters_refuse_a_non_opaque_alpha() -> None:
    # The payload stores three ubyte channels, so an alpha has nowhere to
    # go; accepting one would silently flatten it to opaque.
    application = py_premiere.parse(MINIMAL / "64_caption_style.prproj")
    caption = application.project.sequences[0].caption_tracks[0].captions[0]
    with pytest.raises(ValueError, match="opaque"):
        caption.fill_color = Color(1, 2, 3, 0)
    with pytest.raises(ValueError, match="opaque"):
        caption.background_color = Color(1, 2, 3, 128)
    caption.fill_color = Color(1, 2, 3, 255)
    assert tuple(caption.fill_color) == (1, 2, 3, 255)


def test_the_same_edit_twice_produces_the_same_bytes() -> None:
    # The rewritten block's BinaryHash is derived from the payload, so an
    # edit is reproducible rather than randomised.
    outputs = []
    for _ in range(2):
        application = py_premiere.parse(MINIMAL / "29_captions.prproj")
        application.project.sequences[0].caption_tracks[0].captions[0].text = "same"
        outputs.append(application.project._document.to_bytes())
    assert outputs[0] == outputs[1]


def test_font_size_refuses_a_value_outside_float32() -> None:
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = application.project.sequences[0].caption_tracks[0].captions[0]
    with pytest.raises(ValueError, match="float32"):
        caption.font_size = 1e300


def test_a_corrupt_payload_reads_as_a_value_error() -> None:
    # Every offset in a FlatBuffer comes FROM the buffer, so a corrupt byte
    # steers the reads anywhere. Whatever they land on, a getter may only
    # report it as ValueError - a struct/index/NotImplementedError escaping
    # here is something the caller cannot act on.
    application = py_premiere.parse(MINIMAL / "29_captions.prproj")
    caption = application.project.sequences[0].caption_tracks[0].captions[0]
    pristine = caption._payload()
    refused = 0
    for offset in range(12, 80):
        payload = bytearray(pristine)
        if offset >= len(payload):
            break
        payload[offset] = 0xFF
        caption._write_payload(bytes(payload))
        for name in ("font_size", "font_family", "fill_color"):
            try:
                getattr(caption, name)
            except ValueError:
                refused += 1
            except Exception as error:  # noqa: BLE001
                raise AssertionError(
                    f"{name} leaked {type(error).__name__} from a payload "
                    f"corrupted at byte {offset}: {error}"
                ) from None
    # Not every corruption steers a read out of bounds, but plenty do - if
    # NONE refuse, the bounds checking has gone rather than the test getting
    # lucky with its offsets.
    assert refused > 20, f"only {refused} reads refused a corrupt payload"
