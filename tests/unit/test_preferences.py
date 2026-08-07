"""The Premiere preferences reader."""

from __future__ import annotations

import pytest

from py_premiere.models.preferences import Preferences

_PREFS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PremiereData Version="3">
\t<Preferences ObjectRef="1"/>
\t<Preferences ObjectID="1" ClassID="f06902ec-e637-4744-a586-c26202143e36" Version="30">
\t\t<Properties Version="1">
\t\t\t<BE.Prefs.LabelNames.0>Violet</BE.Prefs.LabelNames.0>
\t\t\t<BE.Prefs.LabelNames.3>Lavender</BE.Prefs.LabelNames.3>
\t\t\t<BE.Prefs.LabelColors.3>8851829</BE.Prefs.LabelColors.3>
\t\t\t<BE.Prefs.LabelDefaults.Still>3</BE.Prefs.LabelDefaults.Still>
\t\t\t<BE.Prefs.LabelDefaults.Video>0</BE.Prefs.LabelDefaults.Video>
\t\t\t<BE.Prefs.StillImages.DurationInSeconds>5</BE.Prefs.StillImages.DurationInSeconds>
\t\t\t<BE.Prefs.StillImages.DefaultFramerate>8475667200</BE.Prefs.StillImages.DefaultFramerate>
\t\t\t<BE.Prefs.StillImages.LockAspectRatio>false</BE.Prefs.StillImages.LockAspectRatio>
\t\t</Properties>
\t</Preferences>
</PremiereData>
"""


@pytest.fixture
def prefs(tmp_path):
    path = tmp_path / "Adobe Premiere Pro Prefs"
    path.write_text(_PREFS_XML, encoding="utf-8")
    return Preferences(path)


def test_typed_getters(prefs) -> None:
    assert prefs.get("BE.Prefs.LabelNames.0") == "Violet"
    assert prefs.get_int("BE.Prefs.LabelColors.3") == 8851829
    assert prefs.get_bool("BE.Prefs.StillImages.LockAspectRatio") is False
    assert prefs.get("BE.Prefs.DoesNotExist") is None


def test_label_helpers(prefs) -> None:
    assert prefs.label_names[3] == "Lavender"
    assert prefs.label_colors[3] == 8851829
    assert prefs.label_default("Still") == 3
    assert prefs.label_default("Video") == 0
    with pytest.raises(ValueError):
        prefs.label_default("Nope")


def test_still_default_out_floors_to_whole_frames(prefs) -> None:
    # 5 s at 29.97 fps -> 149 whole frames, the exact corpus value.
    assert prefs.still_default_out_ticks == 1262874412800


def test_non_prefs_file_raises(tmp_path) -> None:
    bad = tmp_path / "Adobe Premiere Pro Prefs"
    bad.write_text("<PremiereData Version='3'></PremiereData>", encoding="utf-8")
    with pytest.raises(ValueError):
        Preferences(bad)


def test_load_default_machine_prefs() -> None:
    # Best-effort on machines where Premiere ran; always a valid object or
    # None, and the corpus-verified factory values when present.
    preferences = Preferences.load_default()
    if preferences is None:
        pytest.skip("no Premiere preferences on this machine")
    assert preferences.label_default("Bin") is not None
