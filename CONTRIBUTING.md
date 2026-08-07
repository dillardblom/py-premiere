# Contributing Guide

This guide helps you understand the py_premiere codebase and contribute new
features, fixes, and improvements.

## Quick Start

1. **Fork and clone** the repository
2. **Install with dev dependencies**:
   - With uv (recommended): `uv sync --extra dev`
   - With pip: `pip install -e ".[dev]"`
3. **Run tests**: `uv run pytest` (or `pytest`)
4. **Make your changes** following this guide
5. **Submit a pull request**

## Understanding the Codebase

### Architecture Overview

py_premiere transforms `.prproj` files (gzip-compressed XML) into typed
Python objects through a three-stage pipeline:

```
.prproj file > XML layer (xml/) > Object graph > Parsers > Model Classes
```

**Stage 1: XML layer**
- `src/py_premiere/xml/gzip_io.py` - gzip framing (header preserved
  verbatim, stock level-6 deflate)
- `src/py_premiere/xml/document.py` - `PremiereDocument`: the element tree,
  `ObjectID`/`ObjectUID` indexes, `resolve()`, the parse-time self-check
- `src/py_premiere/xml/serializer.py` - reproduces Premiere's exact output
  style (escaping, block-form blobs, expanded empty containers)
- `src/py_premiere/xml/mutations.py` - formatting-preserving tree edits

**Stage 2: Parsers**
- `src/py_premiere/parsers/` - navigate the object graph via the document
  indexes and hand element references to model constructors
- Entry point: `parse()` in `__init__.py`

**Stage 3: Models**
- `src/py_premiere/models/` - classes mirroring Premiere's ExtendScript
  object model (`Application`, `Project`, `ProjectItem`, `Sequence`,
  `Track`, `TrackItem`, `Time`)
- Read/write attributes use the `XmlField` descriptor
  (`models/descriptors.py`) or `@property` setters, validate their input
  (`models/validators.py`), and write through to the backing elements
- Read-only attributes are `@property` without a setter, matching the
  Scripting Guide

**Supporting modules**
- `src/py_premiere/enums/` - enumerations matching ExtendScript values
- `src/py_premiere/cli/` - `pr-inspect`, `pr-compare`, `pr-visualize`,
  `pr-validate`

### Key Concepts

**Object graph**: the XML root `<PremiereData>` holds a flat table of
objects linked by `ObjectRef` -> `ObjectID` (per-save integers) and
`ObjectURef` -> `ObjectUID` (persistent GUIDs). Use
`document.by_object_id` / `by_object_uid` / `resolve()` - never scan the
tree per reference.

**Byte fidelity**: `parse()` then `save()` must reproduce the original file
byte for byte. Parsers never mutate backing elements; the serializer is
validated by a parse-time self-check that refuses files it cannot
reproduce. All mutation goes through descriptors/setters and
`xml/mutations.py`.

**Ground truth**: model semantics are validated against Premiere's own
ExtendScript DOM. `scripts/jsx/export_project_json.jsx` (run via
`scripts/run_in_ppro.ps1`) exports `<fixture>.json`; `pr-validate` and
`tests/read_only/test_ground_truth.py` compare parse output against it.

## Test Structure

Tests are split by folder:

- `tests/read_only/` - parse sample files, never mutate them
- `tests/roundtrip/` - mutate models, `save`, then re-parse fresh from disk
- `tests/unit/` - no sample project needed

Shared helpers live in `tests/helpers.py` (`from helpers import ...`):
`each_sample` parametrizes a test over every local `.prproj` fixture.

Sample corpus:

- `samples/models/` - generated, license-clean, committed fixtures (the CI
  corpus)
- other `samples/` subfolders are local-only fixtures (not redistributable)

## Checks

```sh
uv run ruff check src tests scripts
uv run ruff format src tests scripts
uv run mypy src/py_premiere
uv run pytest
uv run zensical build --strict   # docs
```

Python 3.7 compatibility is required (no walrus operator, no match/case;
modern type hints via `from __future__ import annotations`).
