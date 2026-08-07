"""Unit tests for the `Time` value object."""

from __future__ import annotations

import pytest

from py_premiere.models import TICKS_PER_SECOND, Time


def test_seconds_conversion() -> None:
    assert Time(0).seconds == 0.0
    assert Time(TICKS_PER_SECOND).seconds == 1.0
    assert Time(TICKS_PER_SECOND // 2).seconds == 0.5


def test_equality() -> None:
    assert Time(42) == Time(42)
    assert Time(42) != Time(43)
    assert Time(42) != 42


def test_rejects_non_int_ticks() -> None:
    with pytest.raises(TypeError, match="expected an integer"):
        Time("100")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="expected an integer"):
        Time(True)  # type: ignore[arg-type]


def test_seconds_setter() -> None:
    time = Time()
    time.seconds = 0.5
    assert time.ticks == TICKS_PER_SECOND // 2
    with pytest.raises(TypeError, match="expected a number"):
        time.seconds = "1"  # type: ignore[assignment]


def test_seconds_rejects_a_value_that_overflows_the_tick_scale() -> None:
    time = Time()
    with pytest.raises(ValueError, match="too large"):
        time.seconds = 1e300
    assert time.ticks == 0


def test_addition_and_subtraction() -> None:
    assert Time(10) + Time(5) == Time(15)
    assert Time(5) - Time(10) == Time(-5)
    # Raw numbers are refused: a bare int is ambiguous (ticks? seconds?).
    with pytest.raises(TypeError):
        Time(10) + 5
    with pytest.raises(TypeError):
        Time(10) - 5


def test_scaling_by_a_number() -> None:
    assert Time(10) * 2 == Time(20)
    assert 2 * Time(10) == Time(20)
    assert Time(10) * 0.5 == Time(5)
    # Fractional ticks round half-to-even, like the `seconds` setter.
    assert Time(3) * 0.5 == Time(2)
    assert Time(5) * 0.5 == Time(2)
    # Time * Time would be ticks squared, which has no meaning.
    with pytest.raises(TypeError):
        Time(10) * Time(2)


def test_division() -> None:
    assert Time(10) / 2 == Time(5)
    assert Time(10) / 0.5 == Time(20)
    # Fractional ticks round half-to-even, like the `seconds` setter.
    assert Time(10) / 4 == Time(2)
    with pytest.raises(ZeroDivisionError):
        Time(10) / 0


def test_floor_division() -> None:
    assert Time(10) // 3 == Time(3)
    assert Time(-10) // 3 == Time(-4)
    # int only: `int // float` yields a float, which `ticks` rejects.
    with pytest.raises(TypeError):
        Time(10) // 2.0
    with pytest.raises(ZeroDivisionError):
        Time(10) // 0


def test_negation_and_abs() -> None:
    assert -Time(10) == Time(-10)
    assert abs(Time(-10)) == Time(10)
    assert abs(Time(10)) == Time(10)


def test_ordering() -> None:
    assert Time(1) < Time(2)
    assert Time(2) <= Time(2)
    assert Time(2) > Time(1)
    assert Time(2) >= Time(2)
    assert not Time(1) > Time(2)
    assert sorted([Time(3), Time(1), Time(2)]) == [Time(1), Time(2), Time(3)]
    with pytest.raises(TypeError):
        assert Time(1) < 1


def test_repr() -> None:
    assert repr(Time(42)) == "Time(ticks=42)"


def test_unhashable() -> None:
    # `ticks` is writable; a hashable-but-mutable Time would silently
    # corrupt any set or dict that holds it, so hashing is refused.
    with pytest.raises(TypeError, match="unhashable"):
        hash(Time(1))


#: Ticks per frame at 29.97 fps (the corpus timebase) and at an exact 30.
_TB_2997 = 8475667200
_TB_30 = TICKS_PER_SECOND // 30
_TB_25 = TICKS_PER_SECOND // 25


def test_from_seconds() -> None:
    assert Time.from_seconds(1.0) == Time(TICKS_PER_SECOND)
    assert Time.from_seconds(0.5) == Time(TICKS_PER_SECOND // 2)


def test_frames_round_trip() -> None:
    assert Time.from_frames(30, _TB_25) == Time(30 * _TB_25)
    # A Time timebase (as `SequenceSettings.video_frame_rate` returns) works.
    assert Time.from_frames(2, Time(_TB_25)) == Time(2 * _TB_25)
    assert Time(30 * _TB_25).to_frames(_TB_25) == 30
    # Mid-frame times floor to the containing frame.
    assert Time(30 * _TB_25 + 1).to_frames(_TB_25) == 30
    with pytest.raises(ValueError, match="timebase"):
        Time.from_frames(1, 0)


def test_timecode_non_drop() -> None:
    one_hour = Time.from_timecode("01:00:00:00", _TB_2997)
    # 108000 frames: the value ExtendScript reports for the 19_timecode
    # fixture's start timecode.
    assert one_hour == Time(108000 * _TB_2997)
    assert one_hour.to_timecode(_TB_2997) == "01:00:00:00"
    assert Time(0).to_timecode(_TB_25) == "00:00:00:00"
    assert Time.from_timecode("00:00:01:00", _TB_25) == Time(TICKS_PER_SECOND)


def test_timecode_drop_frame() -> None:
    # 01:00:00;00 drop-frame = 107892 frames, the frames that actually
    # exist (the corpus drop-frame media fact).
    one_hour = Time.from_timecode("01:00:00;00", _TB_2997)
    assert one_hour == Time(107892 * _TB_2997)
    assert one_hour.to_timecode(_TB_2997, drop_frame=True) == "01:00:00;00"
    # The first frame of a dropped minute: frame 1800 displays 00:01:00;02.
    minute = Time(1800 * _TB_2997)
    assert minute.to_timecode(_TB_2997, drop_frame=True) == "00:01:00;02"
    assert Time.from_timecode("00:01:00;02", _TB_2997) == minute
    # Minute 10 is not dropped.
    ten = Time(17982 * _TB_2997)
    assert ten.to_timecode(_TB_2997, drop_frame=True) == "00:10:00;00"
    assert Time.from_timecode("00:10:00;00", _TB_2997) == ten


def test_timecode_validation() -> None:
    with pytest.raises(ValueError, match="timecode"):
        Time.from_timecode("01:00:00", _TB_25)
    with pytest.raises(ValueError, match="out of range"):
        Time.from_timecode("00:00:00:25", _TB_25)
    # Dropped frame numbers do not exist.
    with pytest.raises(ValueError, match="dropped"):
        Time.from_timecode("00:01:00;00", _TB_2997)
    # Drop-frame timecode only exists for the 29.97/59.94 family.
    with pytest.raises(ValueError, match="drop-frame"):
        Time(0).to_timecode(_TB_25, drop_frame=True)
    with pytest.raises(ValueError, match="drop-frame"):
        Time(0).to_timecode(_TB_30, drop_frame=True)
    with pytest.raises(ValueError, match="negative"):
        Time(-1).to_timecode(_TB_25)
