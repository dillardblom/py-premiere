"""The length a sequence reports when something else plays it.

A sequence caches its own length on the `Video`/`AudioSequenceSource`
objects that let it be used as a source, and an edit that lengthens the
timeline has to carry that cache with it.
"""

from __future__ import annotations

from helpers import SAMPLES_DIR, parse_project_fresh

import py_premiere
from py_premiere.models.time import TICKS_PER_SECOND, Time

MINIMAL = SAMPLES_DIR / "models" / "minimal"
ASSETS = SAMPLES_DIR / "models" / "assets"


def _stored(application, sequence_name):
    """Every `OriginalDuration` cached for this sequence, by source tag."""
    project = application.project
    uid = project.sequences[sequence_name].sequence_id
    out = {}
    for element in project._document.root:
        if not element.tag.endswith("SequenceSource"):
            continue
        reference = element.find("SequenceSource/Sequence")
        if reference is not None and reference.get("ObjectURef") == uid:
            out[element.tag] = int(element.findtext("OriginalDuration") or 0)
    return out


def _content(application, sequence_name):
    sequence = application.project.sequences[sequence_name]
    tracks = sequence.video_tracks + sequence.audio_tracks
    return max([clip.end.ticks for track in tracks for clip in track.clips] or [0])


def test_placing_past_the_end_grows_the_cache(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    before = _stored(application, "Seq A")
    assert before == {
        "AudioSequenceSource": 1508668761600,
        "VideoSequenceSource": 1508668761600,
    }

    # The still's marked span is 1.5 s, so it has to land past 6 s to end
    # beyond the 5.94 s the sequence already ran to.
    item = application.project.root_item.children["red_64x36.bmp"]
    placed = (
        application.project.sequences["Seq A"]
        .video_tracks[0]
        .add_clip(item, Time(6 * TICKS_PER_SECOND))
    )
    grown = _content(application, "Seq A")
    assert grown == placed.end.ticks > before["VideoSequenceSource"]

    target = tmp_path / "grown.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert _stored(fresh, "Seq A") == {
        "AudioSequenceSource": grown,
        "VideoSequenceSource": grown,
    }
    # Only the edited sequence moves.
    assert _stored(fresh, "Seq B") == {
        "AudioSequenceSource": 1508668761600,
        "VideoSequenceSource": 1508668761600,
    }


def test_trimming_past_the_end_grows_the_cache(tmp_path) -> None:
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    clip = application.project.sequences["Seq A"].audio_tracks[0].clips[0]
    clip.end = Time(clip.end.ticks + TICKS_PER_SECOND)

    target = tmp_path / "trimmed.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    grown = _content(fresh, "Seq A")
    assert _stored(fresh, "Seq A") == {
        "AudioSequenceSource": grown,
        "VideoSequenceSource": grown,
    }


def test_the_cache_never_shrinks(tmp_path) -> None:
    # Premiere leaves the length alone when the content gets shorter -
    # templates/537 keeps 5228 s on a sequence that is empty in the file.
    application = py_premiere.parse(MINIMAL / "06_api.prproj")
    track = application.project.sequences["Seq A"].video_tracks[0]
    track.remove_clip(track.clips[0])

    target = tmp_path / "shrunk.prproj"
    application.project.save(target)
    fresh = parse_project_fresh(target)
    assert _stored(fresh, "Seq A") == {
        "AudioSequenceSource": 1508668761600,
        "VideoSequenceSource": 1508668761600,
    }


# That the cache follows EDITS only - that parse/save never rewrites it -
# is already covered for every sample by `test_byte_identity.py`.
