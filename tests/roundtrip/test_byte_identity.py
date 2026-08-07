"""Byte-identity round-trip over every local sample.

Payload identity (the decompressed XML) is the contract; full-file identity
additionally requires the platform zlib to reproduce Premiere's deflate
stream (stock level-6 defaults) and is the strong check. See PLAN.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import each_sample, first_mismatch

from py_premiere.xml import PremiereDocument
from py_premiere.xml.gzip_io import decompress_prproj


@each_sample
def test_payload_byte_identity(path: Path) -> None:
    data = path.read_bytes()
    expected, _ = decompress_prproj(data)
    produced = PremiereDocument.from_bytes(data).to_xml_bytes()
    if produced != expected:
        pytest.fail(first_mismatch(produced, expected), pytrace=False)


@each_sample
def test_full_file_byte_identity(path: Path) -> None:
    data = path.read_bytes()
    produced = PremiereDocument.from_bytes(data).to_bytes()
    if produced != data:
        pytest.fail(first_mismatch(produced, data), pytrace=False)
