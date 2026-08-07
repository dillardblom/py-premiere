"""Project.import_files: still-import synthesis parity."""

from __future__ import annotations

import wave

import pytest
from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere import TICKS_PER_SECOND
from py_premiere.enums import VideoFieldType

MINIMAL = SAMPLES_DIR / "models" / "minimal"
BLUE = SAMPLES_DIR / "models" / "assets" / "blue_32x18.bmp"


def test_import_bmp_round_trips(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    items = application.project.import_files([BLUE])
    assert [i.name for i in items] == ["blue_32x18.bmp"]

    target = tmp_path / "imported.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    names = [c.name for c in fresh.project.root_item.children]
    assert names == ["red_64x36.bmp", "blue_32x18.bmp"]
    blue = fresh.project.root_item.children[1]
    assert blue.media_path.name == "blue_32x18.bmp"
    # The template clip carries the still defaults (in 0, out ~5 s).
    assert blue.in_point.ticks == 0
    assert blue.out_point.ticks == 1262874412800


_PREFS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PremiereData Version="3">
\t<Preferences ObjectID="1" ClassID="f06902ec-e637-4744-a586-c26202143e36" Version="30">
\t\t<Properties Version="1">
\t\t\t<BE.Prefs.StillImages.DurationInSeconds>2</BE.Prefs.StillImages.DurationInSeconds>
\t\t\t<BE.Prefs.StillImages.DefaultFramerate>8467200000</BE.Prefs.StillImages.DefaultFramerate>
\t\t</Properties>
\t</Preferences>
</PremiereData>
"""


def test_import_reads_overridden_preferences(tmp_path) -> None:
    # parse(preferences_path=...) overrides the machine-profile discovery:
    # a prefs file declaring 2 s stills at an exact 30 fps must drive the
    # imported item's default out point (60 whole frames).
    prefs_path = tmp_path / "Adobe Premiere Pro Prefs"
    prefs_path.write_text(_PREFS_XML, encoding="utf-8")
    application = py_premiere.parse(
        MINIMAL / "03_one_clip.prproj", preferences_path=prefs_path
    )
    item = application.project.import_files([BLUE])[0]
    assert item.out_point.ticks == 60 * 8467200000


def test_imported_item_can_be_placed(tmp_path) -> None:
    # import -> add_clip composes: the fresh master has in/out marks.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    item = application.project.import_files([BLUE])[0]
    placed = application.project.sequences[0].video_tracks[2].add_clip(item)
    assert placed.name == "blue_32x18.bmp"
    target = tmp_path / "placed.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    v3 = fresh.project.sequences[0].video_tracks[2]
    assert [c.name for c in v3.clips] == ["blue_32x18.bmp"]


def test_imported_item_can_be_removed(tmp_path) -> None:
    # import -> remove_item is a clean inverse (the GC finds all 9 objects).
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    before = len(list(application.project._document.root))
    item = application.project.import_files([BLUE])[0]
    application.project.root_item.remove_item(item)
    assert len(list(application.project._document.root)) == before
    target = tmp_path / "inverse.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert [c.name for c in fresh.project.root_item.children] == ["red_64x36.bmp"]


def test_import_png_round_trips(tmp_path) -> None:
    # PNG differs from BMP only by its codec fourcc and elided AlphaType,
    # matching Premiere's own PNG import of the same file.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    png = SAMPLES_DIR / "models" / "assets" / "green_16x9.png"
    item = application.project.import_files([png])[0]
    target = tmp_path / "png.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    reparsed = next(
        c for c in fresh.project.root_item.children if c.name == "green_16x9.png"
    )
    assert reparsed.media_path.name == "green_16x9.png"
    stream = fresh.project._document.resolve(
        reparsed._clip_elements[0].find("Clip/Source")
    )
    media = fresh.project._document.resolve(stream.find("MediaSource/Media"))
    video_stream = fresh.project._document.resolve(media.find("VideoStream"))
    assert video_stream.findtext("FrameRect") == "0,0,16,9"
    assert video_stream.findtext("CodecType") == "1886283552"
    assert video_stream.find("AlphaType") is None
    assert item.name == "green_16x9.png"


def test_import_wav_round_trips(tmp_path) -> None:
    # 0.5 s mono 16-bit 48 kHz tone: finite media, exact tick duration,
    # audio label default. Premiere's transcript bootstrap and conform-cache
    # paths are elided (regenerated on open).
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    wav = SAMPLES_DIR / "models" / "assets" / "tone_880_hp5.wav"
    item = application.project.import_files([wav])[0]
    assert item.out_point.ticks == 127008000000

    target = tmp_path / "wav.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    reparsed = next(
        c for c in fresh.project.root_item.children if c.name == "tone_880_hp5.wav"
    )
    assert reparsed.media_path.name == "tone_880_hp5.wav"
    assert reparsed.out_point.ticks == 127008000000


def test_imported_wav_can_be_placed(tmp_path) -> None:
    # Unmarked finite media plays 0..duration, frame-snapped, via add_clip.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    wav = SAMPLES_DIR / "models" / "assets" / "tone_880_hp5.wav"
    item = application.project.import_files([wav])[0]
    placed = application.project.sequences[0].audio_tracks[2].add_clip(item)
    timebase = application.project.sequences[0].timebase
    assert placed.duration.ticks == (127008000000 // timebase) * timebase
    target = tmp_path / "placed.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    a3 = fresh.project.sequences[0].audio_tracks[2]
    assert [c.name for c in a3.clips] == ["tone_880_hp5.wav"]


def test_imported_wav_can_be_removed(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    before = len(list(application.project._document.root))
    wav = SAMPLES_DIR / "models" / "assets" / "tone_880_hp5.wav"
    item = application.project.import_files([wav])[0]
    application.project.root_item.remove_item(item)
    assert len(list(application.project._document.root)) == before


def test_import_stereo_and_24bit_wav(tmp_path) -> None:
    # Stereo: L/R channel labels, two secondaries, two channel serializers,
    # ChannelType 1. 24-bit: SampleType elided. Both match Premiere's own
    # imports (pr-compare: 0 objects only-in-py).
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    assets = SAMPLES_DIR / "models" / "assets"
    application.project.import_files(
        [assets / "tone_660_stereo.wav", assets / "tone_550_24bit.wav"]
    )
    target = tmp_path / "variants.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    stereo = next(
        c for c in fresh.project.root_item.children if c.name == "tone_660_stereo.wav"
    )
    core = stereo._clip_elements[0]
    assert (
        core.findtext("AudioChannelLayout")
        == '[{"channellabel":100},{"channellabel":101}]'
    )
    items = core.findall("SecondaryContents/SecondaryContentItem")
    assert len(items) == 2
    # One SecondaryContent per source channel, mapped 0 then 1 - the order
    # Premiere writes for every stereo clip in the corpus.
    assert [document.resolve(ref).findtext("ChannelIndex") for ref in items] == [
        "0",
        "1",
    ]
    deep = next(
        c for c in fresh.project.root_item.children if c.name == "tone_550_24bit.wav"
    )
    source = document.resolve(deep._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("AudioStream"))
    assert stream.find("SampleType") is None


def test_import_51_wav(tmp_path) -> None:
    # 5.1 is a NATIVE channel type: one source clip carrying all six
    # channels, labels 100-105, ChannelType 2, and a chain that gains the
    # channel-volume component plus a repeat of the layout. Matches
    # Premiere's own 5.1 import (pr-compare: 0 objects only-in-either).
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    surround = SAMPLES_DIR / "models" / "assets" / "tone_220_51.wav"
    application.project.import_files([surround])
    target = tmp_path / "surround.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    item = next(
        c for c in fresh.project.root_item.children if c.name == "tone_220_51.wav"
    )
    assert len(item._clip_elements) == 1
    expected_layout = (
        "[" + ",".join(f'{{"channellabel":{100 + i}}}' for i in range(6)) + "]"
    )
    assert item._clip_elements[0].findtext("AudioChannelLayout") == expected_layout
    master = item._master_element
    chain = document.resolve(master.find("AudioComponentChains/AudioComponentChain"))
    assert chain.findtext("DefaultChannelVolumeComponentID") == "2"
    assert chain.findtext("ChannelType") == "2"
    assert chain.findtext("AudioChannelLayout") == expected_layout
    groups = document.resolve(master.find("AudioClipChannelGroups"))
    vectors = groups.findall("ClipChannelVectors/ClipChannelVectorItem")
    assert len(vectors) == 1
    vector = document.resolve(vectors[0])
    assert vector.findtext("ChannelType") == "2"
    channels = [
        document.resolve(ref) for ref in vector.findall("ClipChannels/ClipChannelItem")
    ]
    assert [c.findtext("mSourceChannelIndex") for c in channels] == list("012345")
    assert {c.findtext("SourceClipIndex") for c in channels} == {"0"}


def test_import_quad_wav_splits_into_mono_clips(tmp_path) -> None:
    # 4 channels is NOT a native channel type, so Premiere imports the file
    # as one MONO source clip per channel - four full media graphs, each
    # reading its own StreamNumber - and the channel groups index them
    # through SourceClipIndex.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    quad = SAMPLES_DIR / "models" / "assets" / "tone_330_quad.wav"
    application.project.import_files([quad])
    target = tmp_path / "quad.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    item = next(
        c for c in fresh.project.root_item.children if c.name == "tone_330_quad.wav"
    )
    assert len(item._clip_elements) == 4
    stream_numbers = []
    for clip in item._clip_elements:
        assert clip.findtext("AudioChannelLayout") == '[{"channellabel":0}]'
        source = document.resolve(clip.find("Clip/Source"))
        media = document.resolve(source.find("MediaSource/Media"))
        # Elided for stream 0, as Premiere writes it.
        stream_numbers.append(media.findtext("StreamNumber"))
        stream = document.resolve(media.find("AudioStream"))
        assert stream.findtext("AudioChannelLayout") == '[{"channellabel":0}]'
    assert stream_numbers == [None, "1", "2", "3"]
    master = item._master_element
    assert len(master.findall("AudioComponentChains/AudioComponentChain")) == 4
    groups = document.resolve(master.find("AudioClipChannelGroups"))
    vectors = [
        document.resolve(ref)
        for ref in groups.findall("ClipChannelVectors/ClipChannelVectorItem")
    ]
    assert [v.findtext("ChannelType") for v in vectors] == ["0"] * 4
    sources = []
    for vector in vectors:
        items = vector.findall("ClipChannels/ClipChannelItem")
        assert len(items) == 1
        sources.append(document.resolve(items[0]).findtext("SourceClipIndex"))
    assert sources == list("0123")


def test_import_float32_wav(tmp_path) -> None:
    # IEEE-float WAV: SampleType 6 (16-bit stamps 3, 24-bit elides it).
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    floating = SAMPLES_DIR / "models" / "assets" / "tone_770_float32.wav"
    item = application.project.import_files([floating])[0]
    assert item.out_point.ticks == 63504000000

    target = tmp_path / "float32.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    reparsed = next(
        c for c in fresh.project.root_item.children if c.name == "tone_770_float32.wav"
    )
    source = document.resolve(reparsed._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("AudioStream"))
    assert stream.findtext("SampleType") == "6"


def test_import_unsupported_wav_raises(tmp_path) -> None:
    eight_bit = tmp_path / "8bit.wav"
    with wave.open(str(eight_bit), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(1)
        writer.setframerate(48000)
        writer.writeframes(b"\x80" * 480)
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    with pytest.raises(NotImplementedError):
        application.project.import_files([eight_bit])


def test_import_h264_mp4(tmp_path) -> None:
    # A decoded stream carries the codec fourcc ('avc1') and the decoder's
    # alpha/orientation answers, where uncompressed AVI leaves them open.
    # Matches Premiere's own MP4 import (pr-compare: 0 only-in-either).
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    movie = SAMPLES_DIR / "models" / "assets" / "bars_64x36_h264.mp4"
    item = application.project.import_files([movie])[0]
    assert item.out_point.ticks == 508032000000

    target = tmp_path / "h264.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    reparsed = next(
        c for c in fresh.project.root_item.children if c.name == "bars_64x36_h264.mp4"
    )
    source = document.resolve(reparsed._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("VideoStream"))
    assert stream.findtext("FrameRect") == "0,0,64,36"
    assert stream.findtext("FrameRate") == "10160640000"
    assert stream.findtext("CodecType") == "1635148593"
    assert stream.findtext("IgnoreAlpha") == "true"
    assert stream.findtext("AlphaType") == "3"
    assert media.find("AudioStream") is None


def test_import_timecoded_mov(tmp_path) -> None:
    # A MOV timecode track (02:00:00:00 at 29.97 - the value Modify >
    # Timecode wrote into the asset for fixture 72) materializes the
    # AlternateStart pair and shifts the media in/out, which is what
    # ExtendScript reports as ProjectItem.startTime.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    movie = SAMPLES_DIR / "models" / "assets" / "bars_64x36_2997tc.mov"
    item = application.project.import_files([movie])[0]
    assert item.out_point.ticks == 508540032000
    assert item.start_time.ticks == 1830744115200000

    target = tmp_path / "timecode.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    reparsed = next(
        c for c in fresh.project.root_item.children if c.name == "bars_64x36_2997tc.mov"
    )
    assert reparsed.start_time.ticks == 1830744115200000
    source = document.resolve(reparsed._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    assert media.findtext("AlternateStart") == "1830744115200000"
    assert media.findtext("UseAlternateStart") == "true"
    logging_info = document.resolve(reparsed._master_element.find("LoggingInfo"))
    assert logging_info.findtext("TimecodeFormat") == "103"
    assert logging_info.findtext("MediaInPoint") == "1830744115200000"
    assert logging_info.findtext("MediaOutPoint") == "1831252655232000"
    assert logging_info.findtext("MediaFrameRate") == "8475667200"


def test_import_prores(tmp_path) -> None:
    # Every codec gets its own VideoStream shape: ProRes carries the fourcc
    # and the orientation but none of H.264's alpha fields, and reports the
    # plain RGB-Full colour space. Matches Premiere's own ProRes import
    # (pr-compare: 0 objects only-in-either).
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    movie = SAMPLES_DIR / "models" / "assets" / "bars_64x36_prores.mov"
    application.project.import_files([movie])
    target = tmp_path / "prores.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    item = next(
        c for c in fresh.project.root_item.children if c.name == "bars_64x36_prores.mov"
    )
    source = document.resolve(item._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("VideoStream"))
    assert stream.findtext("CodecType") == str(int.from_bytes(b"apch", "big"))
    assert stream.findtext("OriginalImageOrientationType") == "1"
    assert stream.find("IgnoreAlpha") is None
    assert stream.find("AlphaType") is None
    assert stream.find("FieldTypeIsUncertain") is None
    assert stream.find("OriginalFieldType") is None


def test_import_interlaced_media(tmp_path) -> None:
    # Native field dominance is stored as VideoStream/OriginalFieldType (1 =
    # upper first), elided for progressive media. ExtendScript's
    # getFootageInterpretation().fieldType reports DEFAULT either way - it
    # reads the override slot, not the media - so py's field_type is
    # unaffected, exactly like alpha_usage.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    movie = SAMPLES_DIR / "models" / "assets" / "bars_64x36_prores_tff.mov"
    item = application.project.import_files([movie])[0]
    assert item.footage_interpretation.field_type is VideoFieldType.DEFAULT

    target = tmp_path / "interlaced.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    reparsed = next(
        c
        for c in fresh.project.root_item.children
        if c.name == "bars_64x36_prores_tff.mov"
    )
    source = document.resolve(reparsed._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("VideoStream"))
    assert stream.findtext("OriginalFieldType") == "1"
    assert reparsed.footage_interpretation.field_type is VideoFieldType.DEFAULT


def test_import_drop_frame_timecode(tmp_path) -> None:
    # Drop-frame timecode: format 102 rather than 103, and 01:00:00;00 is
    # 107892 frames where the non-drop label is 108000.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    movie = SAMPLES_DIR / "models" / "assets" / "bars_64x36_2997df.mov"
    item = application.project.import_files([movie])[0]
    assert item.start_time.ticks == 107892 * 8475667200

    target = tmp_path / "dropframe.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    reparsed = next(
        c for c in fresh.project.root_item.children if c.name == "bars_64x36_2997df.mov"
    )
    logging_info = document.resolve(reparsed._master_element.find("LoggingInfo"))
    assert logging_info.findtext("TimecodeFormat") == "102"
    assert logging_info.findtext("MediaInPoint") == str(107892 * 8475667200)


def test_import_av_mp4(tmp_path) -> None:
    # Video + audio in one file: TWO source clips on ONE Media (both stream
    # refs), the AAC stream stamped SampleType 7 and given the MEDIA
    # duration, no capture mode, and the AV label default. Matches
    # Premiere's own import (pr-compare: 0 objects only-in-either).
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    movie = SAMPLES_DIR / "models" / "assets" / "bars_64x36_av.mp4"
    application.project.import_files([movie])
    target = tmp_path / "av.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    item = next(
        c for c in fresh.project.root_item.children if c.name == "bars_64x36_av.mp4"
    )
    assert [c.tag for c in item._clip_elements] == ["VideoClip", "AudioClip"]
    video_source = document.resolve(item._clip_elements[0].find("Clip/Source"))
    audio_source = document.resolve(item._clip_elements[1].find("Clip/Source"))
    video_media = document.resolve(video_source.find("MediaSource/Media"))
    audio_media = document.resolve(audio_source.find("MediaSource/Media"))
    assert video_media is audio_media
    audio_stream = document.resolve(video_media.find("AudioStream"))
    assert audio_stream.findtext("SampleType") == "7"
    assert audio_stream.findtext("Duration") == "508032000000"
    assert video_media.findtext("ConformedAudioRate") == "5292000"
    logging_info = document.resolve(item._master_element.find("LoggingInfo"))
    assert logging_info.find("CaptureMode") is None


def test_import_avi_round_trips(tmp_path) -> None:
    # 50 frames at 25 fps: exact tick duration, movie-flavored stream (no
    # IsStill/CodecType, AlphaInfoIsUncertain), video label default.
    # Matches Premiere's own AVI import (pr-compare: 0 only-in-either).
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    avi = SAMPLES_DIR / "models" / "assets" / "bars_48x27.avi"
    item = application.project.import_files([avi])[0]
    assert item.out_point.ticks == 508032000000

    target = tmp_path / "avi.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    reparsed = next(
        c for c in fresh.project.root_item.children if c.name == "bars_48x27.avi"
    )
    document = fresh.project._document
    source = document.resolve(reparsed._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("VideoStream"))
    assert stream.findtext("FrameRect") == "0,0,48,27"
    assert stream.findtext("FrameRate") == "10160640000"
    assert stream.find("IsStill") is None
    assert media.find("Infinite") is None


def test_imported_avi_can_be_placed(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    avi = SAMPLES_DIR / "models" / "assets" / "bars_48x27.avi"
    item = application.project.import_files([avi])[0]
    placed = application.project.sequences[0].video_tracks[2].add_clip(item)
    # 2 s of 25 fps media snapped to whole 29.97 fps sequence frames.
    timebase = application.project.sequences[0].timebase
    assert placed.duration.ticks == (508032000000 // timebase) * timebase


def test_import_missing_file_raises() -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    with pytest.raises(ValueError):
        application.project.import_files([MINIMAL / "nope.bmp"])


def test_import_unsupported_still_format_raises(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    other = tmp_path / "frame.tga"
    other.write_bytes(b"not media")
    with pytest.raises(NotImplementedError):
        application.project.import_files([other])


def test_import_damaged_movie_raises(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    other = tmp_path / "clip.mov"
    other.write_bytes(b"not media")
    with pytest.raises(ValueError):
        application.project.import_files([other])


def test_save_updates_the_project_name_and_path(tmp_path) -> None:
    application = py_premiere.new()
    assert application.project.name == "untitled.prproj"
    target = tmp_path / "renamed.prproj"
    application.project.save(target)
    assert application.project.path == target
    assert application.project.name == "renamed.prproj"
    assert application.project.root_item.name == "renamed.prproj"


def test_import_relative_path_follows_the_save_location(tmp_path) -> None:
    # Premiere re-derives RelativePath against the destination on every save
    # (native ground truth); an import must not bake in the old directory.
    application = py_premiere.new()
    application.project.import_files([BLUE])
    nested = tmp_path / "one" / "two"
    nested.mkdir(parents=True)
    target = nested / "project.prproj"
    application.project.save(target)

    text = parse_project_fresh(target).project._document.to_xml_bytes().decode("utf-8")
    stored = [
        line.strip()[len("<RelativePath>") : -len("</RelativePath>")]
        for line in text.splitlines()
        if "<RelativePath>" in line
    ]
    assert stored
    resolved = (target.parent / stored[0].replace("\\", "/")).resolve()
    assert resolved == BLUE.resolve()


def test_parsed_project_still_saves_byte_identically(tmp_path) -> None:
    # The relative-path rewrite must not touch media that was already in the
    # file, or an untouched round-trip would stop being byte-exact.
    source = MINIMAL / "03_one_clip.prproj"
    application = py_premiere.parse(source)
    target = tmp_path / "copy.prproj"
    application.project.save(target)
    assert target.read_bytes() == source.read_bytes()


def test_import_mxf(tmp_path) -> None:
    # MXF is KLV-framed, not ISO base media, so it has its own reader: the
    # display raster (MPEG-2 pads the STORED one to a macroblock multiple),
    # the edit rate, the track duration and the material package's UMID,
    # which Premiere records as the clip's ClipID. Matches Premiere's own
    # MXF import (pr-compare: 0 objects only-in-either).
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    movie = SAMPLES_DIR / "models" / "assets" / "bars_64x36_mpeg2.mxf"
    item = application.project.import_files([movie])[0]
    assert item.out_point.ticks == 254016000000

    target = tmp_path / "mxf.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    reparsed = next(
        c for c in fresh.project.root_item.children if c.name == "bars_64x36_mpeg2.mxf"
    )
    source = document.resolve(reparsed._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("VideoStream"))
    # 64x36 display, even though MPEG-2 stores the frame 64x48.
    assert stream.findtext("FrameRect") == "0,0,64,36"
    assert stream.findtext("CodecType") == str(int.from_bytes(b"MPEG", "big"))
    logging_info = document.resolve(reparsed._master_element.find("LoggingInfo"))
    clip_id = logging_info.findtext("ClipID")
    assert clip_id and clip_id.startswith("060A2B34")


def test_import_h265_and_dnxhr(tmp_path) -> None:
    # Two more codec profiles: H.265 reports what H.264 does but is stamped
    # 'HEVC' rather than its container fourcc 'hvc1', and DNxHR reports what
    # ProRes does. Both match Premiere's own imports.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    assets = SAMPLES_DIR / "models" / "assets"
    application.project.import_files(
        [assets / "bars_64x36_h265.mov", assets / "bars_256x144_dnxhr.mov"]
    )
    target = tmp_path / "codecs.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document

    def stream_of(name):
        item = next(c for c in fresh.project.root_item.children if c.name == name)
        source = document.resolve(item._clip_elements[0].find("Clip/Source"))
        media = document.resolve(source.find("MediaSource/Media"))
        return document.resolve(media.find("VideoStream"))

    hevc = stream_of("bars_64x36_h265.mov")
    assert hevc.findtext("CodecType") == str(int.from_bytes(b"HEVC", "big"))
    assert hevc.findtext("AlphaType") == "3"
    dnxhr = stream_of("bars_256x144_dnxhr.mov")
    assert dnxhr.findtext("CodecType") == str(int.from_bytes(b"AVdh", "big"))
    assert dnxhr.findtext("FrameRect") == "0,0,256,144"
    # The ProRes/DNxHR family stamps none of H.264's alpha fields.
    assert dnxhr.find("AlphaType") is None
    assert dnxhr.find("IgnoreAlpha") is None


def test_import_jpeg_still(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    jpeg = SAMPLES_DIR / "models" / "assets" / "bars_64x36.jpg"
    application.project.import_files([jpeg])
    target = tmp_path / "jpeg.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    item = next(
        c for c in fresh.project.root_item.children if c.name == "bars_64x36.jpg"
    )
    source = document.resolve(item._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("VideoStream"))
    assert stream.findtext("FrameRect") == "0,0,64,36"
    assert stream.findtext("CodecType") == str(int.from_bytes(b"jpeg", "big"))
    assert stream.findtext("IsStill") == "true"


def test_import_gif_and_aiff(tmp_path) -> None:
    # GIF decodes to the SAME raster codec as BMP ('RGP ', AlphaType 1);
    # AIFF is big-endian PCM, which Premiere marks with its own SampleType
    # (11, where a 16-bit WAV is 3). Both match Premiere's own imports.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    assets = SAMPLES_DIR / "models" / "assets"
    application.project.import_files(
        [assets / "bars_64x36.gif", assets / "tone_440.aiff"]
    )
    target = tmp_path / "gif_aiff.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document

    gif = next(
        c for c in fresh.project.root_item.children if c.name == "bars_64x36.gif"
    )
    source = document.resolve(gif._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("VideoStream"))
    assert stream.findtext("CodecType") == str(int.from_bytes(b"RAW ", "big"))
    assert stream.findtext("AlphaType") == "1"
    assert stream.findtext("FrameRect") == "0,0,64,36"

    aiff = next(
        c for c in fresh.project.root_item.children if c.name == "tone_440.aiff"
    )
    assert aiff.out_point.ticks == 127008000000
    source = document.resolve(aiff._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    audio = document.resolve(media.find("AudioStream"))
    assert audio.findtext("SampleType") == "11"
    assert audio.findtext("FrameRate") == "5292000"


def test_import_psd_still(tmp_path) -> None:
    # PSD comes in as codec 'UNKN' and is the only still Premiere writes
    # WITHOUT FieldTypeIsUncertain, so the still table is a profile per
    # format rather than just a fourcc.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    psd = SAMPLES_DIR / "models" / "assets" / "bars_64x36.psd"
    application.project.import_files([psd])
    target = tmp_path / "psd.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    item = next(
        c for c in fresh.project.root_item.children if c.name == "bars_64x36.psd"
    )
    source = document.resolve(item._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("VideoStream"))
    assert stream.findtext("FrameRect") == "0,0,64,36"
    assert stream.findtext("CodecType") == str(int.from_bytes(b"UNKN", "big"))
    assert stream.findtext("IsStill") == "true"
    assert stream.find("FieldTypeIsUncertain") is None
    assert stream.find("AlphaType") is None


def test_import_mjpeg_avi(tmp_path) -> None:
    # MJPEG in an AVI reports 'MPEG' - the SAME fourcc as MPEG-2 in an MXF -
    # but with a constant OriginalFieldType and no orientation, which is why
    # the profile table is keyed by (container, codec).
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    avi = SAMPLES_DIR / "models" / "assets" / "bars_64x36_mjpeg.avi"
    application.project.import_files([avi])
    target = tmp_path / "mjpeg.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    item = next(
        c for c in fresh.project.root_item.children if c.name == "bars_64x36_mjpeg.avi"
    )
    source = document.resolve(item._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("VideoStream"))
    assert stream.findtext("CodecType") == str(int.from_bytes(b"MPEG", "big"))
    assert stream.findtext("OriginalFieldType") == "3"
    assert stream.find("OriginalImageOrientationType") is None
    # The uncompressed AVI in the same container family stamps no codec.
    application2 = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    plain = SAMPLES_DIR / "models" / "assets" / "bars_48x27.avi"
    application2.project.import_files([plain])
    target2 = tmp_path / "plain_avi.prproj"
    application2.project.save(target2)
    fresh2 = parse_project_fresh(target2)
    document2 = fresh2.project._document
    item2 = next(
        c for c in fresh2.project.root_item.children if c.name == "bars_48x27.avi"
    )
    source2 = document2.resolve(item2._clip_elements[0].find("Clip/Source"))
    media2 = document2.resolve(source2.find("MediaSource/Media"))
    stream2 = document2.resolve(media2.find("VideoStream"))
    assert stream2.find("CodecType") is None


def test_import_tiff_still(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    tif = SAMPLES_DIR / "models" / "assets" / "bars_64x36.tif"
    application.project.import_files([tif])
    target = tmp_path / "tif.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    item = next(
        c for c in fresh.project.root_item.children if c.name == "bars_64x36.tif"
    )
    source = document.resolve(item._clip_elements[0].find("Clip/Source"))
    media = document.resolve(source.find("MediaSource/Media"))
    stream = document.resolve(media.find("VideoStream"))
    assert stream.findtext("FrameRect") == "0,0,64,36"
    assert stream.findtext("CodecType") == str(int.from_bytes(b"tiff", "big"))


def test_import_m4a_and_wma(tmp_path) -> None:
    # Compressed audio: the sample type is a constant per codec (what it
    # decodes TO - 7 for the float codecs, 3 for WMA's 16-bit int), and the
    # duration must be the TRIMMED one. Both match Premiere's own imports.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    assets = SAMPLES_DIR / "models" / "assets"
    items = application.project.import_files(
        [assets / "tone_440.m4a", assets / "tone_440.wma"]
    )
    assert items[0].out_point.ticks == 127008000000
    assert items[1].out_point.ticks == 127262016000

    target = tmp_path / "compressed.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    document = fresh.project._document
    for name, sample_type in (("tone_440.m4a", "7"), ("tone_440.wma", "3")):
        item = next(c for c in fresh.project.root_item.children if c.name == name)
        source = document.resolve(item._clip_elements[0].find("Clip/Source"))
        media = document.resolve(source.find("MediaSource/Media"))
        stream = document.resolve(media.find("AudioStream"))
        assert stream.findtext("SampleType") == sample_type


def test_compressed_audio_imports_with_premieres_own_duration() -> None:
    # MP3 and raw AAC were refused until their trims were measured against
    # Premiere at four durations each: an MP3's encoder tag states its trim
    # exactly, and Premiere drops exactly one frame of AAC priming.
    application = py_premiere.parse(MINIMAL / "03_one_clip.prproj")
    assets = SAMPLES_DIR / "models" / "assets"
    items = application.project.import_files(
        [assets / "tone_440.mp3", assets / "tone_440.aac"]
    )
    assert len(items) == 2
    rate = 48000
    # 22 frames minus 576 priming and 768 padding.
    assert items[0].out_point.ticks == round(24000 / rate * TICKS_PER_SECOND)
    # 25 declared frames minus one of priming.
    assert items[1].out_point.ticks == round(24576 / rate * TICKS_PER_SECOND)


def test_import_into_a_freshly_created_bin(tmp_path) -> None:
    # A ProjectItem is sized by its children, so an EMPTY bin is falsy;
    # selecting the target with `or` sent the import to the root instead -
    # and only for a bin that had no children yet.
    application = py_premiere.parse(MINIMAL / "01_empty.prproj")
    target = application.project.root_item.add_bin("Media")
    imported = application.project.import_files([BLUE], target_bin=target)
    assert imported[0]._parent is target
    assert [c.name for c in target.children] == [BLUE.name]

    output = tmp_path / "into_bin.prproj"
    application.project.save(output)
    fresh = parse_project_fresh(output)
    media = fresh.project.root_item.children.get("Media")
    assert media is not None
    assert [c.name for c in media.children] == [BLUE.name]
    assert BLUE.name not in [c.name for c in fresh.project.root_item.children]


def test_import_into_a_bin_that_already_has_children(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "01_empty.prproj")
    target = application.project.root_item.add_bin("Media")
    application.project.import_files([BLUE], target_bin=target)
    application.project.import_files(
        [SAMPLES_DIR / "models" / "assets" / "green_16x9.png"], target_bin=target
    )
    assert len(target.children) == 2
