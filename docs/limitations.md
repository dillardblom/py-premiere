# Known Limitations

Limitations that come from parsing a `.prproj` file rather than querying a
running Premiere Pro instance. These values are not stored in the file, so
no parser can recover them.

## Session-assigned identifiers

| Attribute | Reason |
|---|---|
| `ProjectItem.node_id` | Premiere assigns node IDs per session at load and ignores the stored values on reopen. `py_premiere` reproduces them only for a freshly saved project (best-effort), and returns `None` otherwise. |
| `Project.active_sequence` | No dedicated key exists; the frontmost sequence is inferred from the open-sequence list in the project's property bag (heuristic, occasionally ambiguous when the list holds duplicates). |

Both are excluded from ground-truth validation for this reason.

## Runtime-only state

Attributes that reflect the live application, with no file representation:

| Attribute | Reason |
|---|---|
| `app.version` / `app.build` | Application build, not project data |
| selection state | Which items/clips are selected |
| player position | Source/Program monitor playhead |
| panel / workspace state | Non-persisting UI |
| `SourceMonitor`, `ProjectManager`, Encoder, Team Projects | Runtime service objects |

## Unreproducible files are refused

To guarantee the byte-fidelity round-trip, `parse()` re-serializes the
document at load and compares it to the original. A file containing
constructs the serializer cannot reproduce exactly (unusual comment or
CDATA idioms, prolog variants) is refused at parse time rather than parsed
into something that would not round-trip.

## Not yet parsed

Surfaces that exist in the format but are not decoded yet (tracked in the
project TODO): popup and menu parameter values, and the binary arbitrary
payloads (Lumetri and friends - the text and shape-path ones do decode).
These raise no error - they are simply absent from the model until
implemented.

## Writes Premiere reverts on open

Premiere validates some stored values against live state when it opens a
project, and rewrites them on its next save. Writing these through
`py_premiere` produces a correct file, but the value does not survive a
Premiere open-and-resave:

* **A start-time override on media with an embedded timecode.**
  `ProjectItem.start_time` writes `Media/AlternateStart`, exactly as
  ExtendScript's `setStartTime` does - and for media carrying an embedded
  timecode, Premiere re-reads the media on open and restores the embedded
  value. ExtendScript's own edit reverts the same way. The GUI's Modify >
  Timecode persists precisely because it does NOT rely on the project: it
  rewrites the source file itself - the QuickTime `tmcd` sample gets the
  new frame count and an XMP packet with `xmpDM:altTimecode` is embedded -
  and then stores the same value in `AlternateStart` (fixture
  `72_modify_timecode` against the before/after asset). Editing source
  media is outside a project library's scope, so this stays a limitation.
* **A time display format illegal for the sequence's frame rate** (e.g.
  23.976 timecode on a 29.97 sequence): reverted to the rate's own format.

## Two values ExtendScript reports that the file does not hold

`pr-validate` calls these out as known divergences rather than failures:

* **A colour label that was never stored.** Premiere stamps a label when it
  creates an item, so items normally carry one and py reads it exactly. When
  nothing is stored, ExtendScript falls back to the LIVE
  `BE.Prefs.LabelDefaults.<kind>` preference - verified on two generator items
  with no stored label, which ES reports as the `Still` (3) and `AV` (1)
  defaults. py reports `0` there, because the file says nothing. The
  categorisation itself is not reproducible from the file: a universal
  counting leader has both a video and an audio stream yet ES reports the
  `Video` default for it, so no stream-based rule fits the evidence.
* **The duration of continuous-time media.** Media flagged
  `IsContinuousTime` (a counting leader) stores a placeholder duration - 6
  frames - while ExtendScript reports the real 11 seconds, a number that
  appears nowhere in the project. It comes from the importer, not the file.

XMP metadata is a different case, and no amount of parsing will fix it:
Premiere writes an item's XMP packet into the **media file**, not into the
project. `setXMPMetadata` followed by a save leaves no trace anywhere in the
`.prproj`, so there is nothing in a project file to read.
