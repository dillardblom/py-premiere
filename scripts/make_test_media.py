"""Generate tiny license-clean media assets for the generated sample corpus.

Premiere imports BMP stills fine, and a hand-written BMP needs no encoder.
Run from the repo root: `uv run python scripts/make_test_media.py`.
"""

from __future__ import annotations

import struct
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "samples" / "models" / "assets"


def write_bmp(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    row = bytes(reversed(rgb)) * width
    row += b"\x00" * ((4 - len(row) % 4) % 4)
    pixels = row * height
    header_size = 14 + 40
    file_size = header_size + len(pixels)
    header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, header_size)
    dib = struct.pack(
        "<IiiHHIIiiII", 40, width, height, 1, 24, 0, len(pixels), 2835, 2835, 0, 0
    )
    path.write_bytes(header + dib + pixels)


def write_wav(path: Path, seconds: float, frequency: float) -> None:
    import math
    import wave

    rate = 48000
    frames = bytearray()
    for i in range(int(rate * seconds)):
        sample = int(8000 * math.sin(2 * math.pi * frequency * i / rate))
        frames += struct.pack("<h", sample)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(bytes(frames))


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    write_bmp(ASSETS / "red_64x36.bmp", 64, 36, (200, 30, 30))
    print(f"wrote {ASSETS / 'red_64x36.bmp'}")
    write_wav(ASSETS / "tone_440_1s.wav", 1.0, 440.0)
    print(f"wrote {ASSETS / 'tone_440_1s.wav'}")


if __name__ == "__main__":
    main()
