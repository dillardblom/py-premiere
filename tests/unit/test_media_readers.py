"""The media-header readers behind `Project.import_files`."""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR

from py_premiere.models.media_import import (
    WAVE_FORMAT_IEEE_FLOAT,
    WAVE_FORMAT_PCM,
    read_aiff_info,
    read_audio_info,
    read_avi_info,
    read_bmp_size,
    read_gif_size,
    read_jpeg_size,
    read_m4a_info,
    read_mp3_info,
    read_mp4_info,
    read_mxf_info,
    read_png_size,
    read_psd_size,
    read_tiff_size,
    read_wav_info,
    read_wma_info,
)

ASSETS = SAMPLES_DIR / "models" / "assets"


def test_reads_mono_pcm_wav() -> None:
    info = read_wav_info((ASSETS / "tone_880_hp5.wav").read_bytes())
    assert info.sample_rate == 48000
    assert info.frames == 24000
    assert info.channels == 1
    assert info.sample_width == 2
    assert info.format_tag == WAVE_FORMAT_PCM
    assert info.channel_mask == 0


def test_reads_extensible_multichannel_wav() -> None:
    # WAVE_FORMAT_EXTENSIBLE resolves to the tag in its SubFormat GUID and
    # carries the speaker mask (5.1 = FL FR FC LFE BL BR).
    info = read_wav_info((ASSETS / "tone_220_51.wav").read_bytes())
    assert info.channels == 6
    assert info.format_tag == WAVE_FORMAT_PCM
    assert info.channel_mask == 0x3F
    assert (
        read_wav_info((ASSETS / "tone_330_quad.wav").read_bytes()).channel_mask == 0x33
    )


def test_reads_float_wav() -> None:
    info = read_wav_info((ASSETS / "tone_770_float32.wav").read_bytes())
    assert info.format_tag == WAVE_FORMAT_IEEE_FLOAT
    assert info.sample_width == 4
    assert info.frames == 12000


def test_rejects_non_wav() -> None:
    with pytest.raises(ValueError):
        read_wav_info(b"RIFF\x00\x00\x00\x00AVI LIST")


def test_reads_mp4() -> None:
    info = read_mp4_info((ASSETS / "bars_64x36_h264.mp4").read_bytes())
    assert (info.width, info.height) == (64, 36)
    assert info.timescale // info.frame_duration == 25
    assert info.frames == 50
    assert info.codec == "avc1"
    assert info.start_timecode == 0
    assert info.drop_frame is False
    assert info.field_order == 0
    assert info.audio is None


def test_reads_mov_timecode_track() -> None:
    # 29.97 stays exact as 30000/1001, and the tmcd sample holds the start
    # timecode as a frame count (02:00:00:00 = 216000 frames - the asset
    # carries the value Premiere's Modify > Timecode wrote into it for the
    # 72_modify_timecode fixture, which rewrites the tmcd sample and embeds
    # XMP altTimecode rather than storing anything project-side).
    info = read_mp4_info((ASSETS / "bars_64x36_2997tc.mov").read_bytes())
    assert (info.timescale, info.frame_duration) == (30000, 1001)
    assert info.frames == 60
    assert info.start_timecode == 216000
    assert info.drop_frame is False


def test_reads_drop_frame_timecode() -> None:
    # Drop-frame counts the frames that exist, so the same 01:00:00 label is
    # 107892 frames rather than 108000.
    info = read_mp4_info((ASSETS / "bars_64x36_2997df.mov").read_bytes())
    assert info.drop_frame is True
    assert info.start_timecode == 107892


def test_reads_prores_and_field_order() -> None:
    progressive = read_mp4_info((ASSETS / "bars_64x36_prores.mov").read_bytes())
    assert progressive.codec == "apch"
    assert progressive.field_order == 0
    # The `fiel` extension of the interlaced encode says top field first,
    # which is VideoFieldType.UPPER_FIRST.
    interlaced = read_mp4_info((ASSETS / "bars_64x36_prores_tff.mov").read_bytes())
    assert interlaced.codec == "apch"
    assert interlaced.field_order == 1


def test_reads_movie_audio_track() -> None:
    info = read_mp4_info((ASSETS / "bars_64x36_av.mp4").read_bytes())
    assert info.audio is not None
    assert info.audio.sample_rate == 48000
    assert info.audio.channels == 2


def test_rejects_non_movie() -> None:
    with pytest.raises(ValueError):
        read_mp4_info(b"\x00\x00\x00\x10ftypmp42" + b"\x00" * 8)


def test_reads_avi() -> None:
    assert read_avi_info((ASSETS / "bars_48x27.avi").read_bytes()) == (
        48,
        27,
        25,
        50,
        "DIB ",
    )
    # A compressed AVI reports its own stream fourcc, which selects a
    # different VideoStream profile from the uncompressed one.
    mjpeg = read_avi_info((ASSETS / "bars_64x36_mjpeg.avi").read_bytes())
    assert mjpeg[4] == "MJPG"


def test_reads_m4a_edit_list() -> None:
    # The packet count OVERSTATES an AAC track (encoder priming plus
    # padding); the edit list states the trimmed span, which is what
    # Premiere reports - exactly 0.5 s for this asset.
    info = read_audio_info((ASSETS / "tone_440.m4a").read_bytes(), ".m4a")
    assert info.sample_rate == 48000
    assert info.frames == 24000


def test_reads_wma() -> None:
    info = read_audio_info((ASSETS / "tone_440.wma").read_bytes(), ".wma")
    assert info.sample_rate == 48000
    assert info.channels == 1
    assert info.frames == 24048


def test_mp3_duration_drops_the_encoder_trim() -> None:
    # The Xing/Info tag counts 22 frames (25344 samples) but the encoder tag
    # after it declares 576 samples of priming and 768 of padding, and what
    # plays is what is left: exactly 0.5 s, which is what Premiere reports.
    # ffmpeg signs that tag `Lavc...`, not `LAME` - keying on the signature
    # rather than its fixed offset is what hid it.
    mp3 = read_audio_info((ASSETS / "tone_440.mp3").read_bytes(), ".mp3")
    assert mp3.frames == 22 * 1152 - (576 + 768)
    assert mp3.frames == 24000
    assert mp3.frames / mp3.sample_rate == 0.5


def test_aac_duration_drops_one_frame_of_priming() -> None:
    # A raw ADTS stream cannot declare its trim, so the TRUE duration is not
    # recoverable. Premiere drops exactly one 1024-sample frame of decoder
    # priming - measured identical at four durations - and matching Premiere
    # is the bar, so the clip is a fraction longer than the audio really is.
    aac = read_audio_info((ASSETS / "tone_440.aac").read_bytes(), ".aac")
    assert aac.frames == 25 * 1024 - 1024


#: Every reader, with an asset it should parse. These take UNTRUSTED file
#: bytes, so a malformed one must read as a ValueError, never as a
#: struct/index/zero-division error from inside the parser.
_READERS = [
    ("red_64x36.bmp", read_bmp_size),
    ("green_16x9.png", read_png_size),
    ("bars_64x36.gif", read_gif_size),
    ("bars_64x36.jpg", read_jpeg_size),
    ("bars_64x36.psd", read_psd_size),
    ("bars_64x36.tif", read_tiff_size),
    ("bars_48x27.avi", read_avi_info),
    ("bars_64x36_h264.mp4", read_mp4_info),
    ("bars_64x36_mpeg2.mxf", read_mxf_info),
    ("tone_440_1s.wav", read_wav_info),
    ("tone_440.aiff", read_aiff_info),
    # The compressed readers walk the most file-controlled offsets in the
    # module (Xing/VBRI headers, ASF object chains), so they belong here
    # most of all.
    ("tone_440.mp3", read_mp3_info),
    ("tone_440.m4a", read_m4a_info),
    ("tone_440.wma", read_wma_info),
]


@pytest.mark.parametrize("name,reader", _READERS, ids=[n for n, _ in _READERS])
def test_readers_refuse_truncation_cleanly(name, reader) -> None:
    data = (SAMPLES_DIR / "models" / "assets" / name).read_bytes()
    for length in (0, 1, 4, 7, 8, 16, 17, 20, 28, 31, 32, 64, 120, 127, 286):
        if length >= len(data):
            break
        try:
            reader(data[:length])
        except (ValueError, NotImplementedError):
            continue
        except Exception as error:  # noqa: BLE001
            raise AssertionError(
                f"{name} truncated to {length} leaked {type(error).__name__}: {error}"
            ) from None


def test_wav_with_a_zero_sample_rate_is_refused() -> None:
    data = bytearray(
        (SAMPLES_DIR / "models" / "assets" / "tone_440_1s.wav").read_bytes()
    )
    data[24:28] = b"\x00\x00\x00\x00"  # the fmt chunk's sample rate
    with pytest.raises(ValueError, match="sample rate"):
        read_wav_info(bytes(data))


def test_tiff_with_a_hostile_ifd_offset_is_refused() -> None:
    data = bytearray(
        (SAMPLES_DIR / "models" / "assets" / "bars_64x36.tif").read_bytes()
    )
    data[4:8] = b"\xff\xff\xff\xff"  # the IFD offset, taken straight from the file
    with pytest.raises(ValueError):
        read_tiff_size(bytes(data))
