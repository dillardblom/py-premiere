# UXP harness for py-premiere

A second Premiere automation transport alongside the ExtendScript (`jsx/`)
one. UXP (Premiere 25.6+) reaches DOM surfaces ExtendScript never had -
transitions, keyframe creation, footage interpretation, captions - so it is
used to generate fixtures ExtendScript cannot, and as a second ground-truth
source. ExtendScript stays the primary parity target (the committed
`*.json` ground truth is ExtendScript-shaped).

## Transport (empirically established 2026-07-20, Premiere 26.3)

The dev-load path is `@adobe/uxp-devtools-cli` (v1.2.0) loading the harness
plugin into a running GUI Premiere. Findings:

- **UXP developer mode must be on**, once, as admin: `{"developer": true}`
  at `C:\Program Files\Common Files\Adobe\UXP\Developer\settings.json`
  (or `npx uxp devtools enable`). The runner refuses to launch without it.
- **The CLI's postinstall is broken** (undeclared `tar`/`fs-extra` deps).
  Install with `npm install --ignore-scripts`, then run
  `node_modules/@adobe/uxp-devtools-helper/scripts/devtools_setup.js` to
  extract the native add-on. `run_uxp_in_ppro.ps1` bootstraps this.
- **Bare command-line project open is broken**: `Premiere.exe <path.prproj>`
  raises a blocking "This file path does not exist on disk" modal even for a
  valid, existing file, and UXP `Project.open()` from the Home screen hangs
  or returns "Failed to open the project". The reliable open is the
  ExtendScript `app.openDocument(path, true, true, true)` (suppresses the
  conversion / locate-media / not-found dialogs) - so the runner launches
  with `/C es.processFile open_project.jsx` (project via `PYPREMIERE_OPEN`
  env var), waits for the jsx's ready marker, THEN loads the plugin, which
  reads `getActiveProject()`. Hybrid jsx-open + UXP-DOM.
- **CDP is reachable** for debugging: `uxp plugin debug` returns a
  `ws=host/path` URL (note: `ws=` not `ws://`); attach a WebSocket, wait for
  `Runtime.executionContextCreated` (isDefault), then `Runtime.evaluate`
  with that `contextId`. See the session scratch `cdp_probe.js`.
- **BOM matters**: write `job.json` with `UTF8Encoding($false)` - a BOM
  makes the plugin's `JSON.parse` throw.

## Files

- `run_uxp_in_ppro.ps1` - the runner (parallels `run_in_ppro.ps1`)
- `open_project.jsx` - silent project opener (jsx, launched via `/C`)
- `harness/` - the dev-loaded plugin; `index.js` runs `payload.js` against
  `job.json` and writes the marker (committed; `payload.js`/`job.json`/
  `.uxprc` are generated and gitignored)
- `payloads/` - `hello.js` (transport smoke test), `export_dom.js` (ground
  truth), `make_transition_fixture.js` (first ES-impossible fixture)
- `package.json` - pins the CLI; `node_modules/` is gitignored

## Usage

```powershell
powershell -File scripts/run_uxp_in_ppro.ps1 `
  -PayloadPath scripts/uxp/payloads/export_dom.js `
  -ResultPath out.json `
  -ProjectPath samples/models/minimal/06_api.prproj
```

## UXP vs ExtendScript DOM calibration (06_api, 2026-07-20)

The two DOMs agree on every value both report - clip in/out ticks, marker
name/type/start, track names+ids, sequence work in/out, guids all match
exactly. Systematic differences to account for when using UXP as ground
truth:

- **Path prefix**: UXP `project.path` is the Windows extended-length form
  `\\?\C:\...`; ExtendScript and py give plain `C:\...`. Strip `\\?\`.
- **zeroPoint**: UXP `getZeroPoint()` returns a clean `TickTime`; the ES
  exporter recorded `{}` (its `timeObject` threw on the String). UXP is the
  better source here (Seq A zeroPoint = 245794348800 ticks).
- **Marker duration**: UXP exposes `getDuration()` natively (comment = 1s);
  ES ground truth stores `end` and py derives `end = start + mDuration`.
  UXP duration == ES (end - start), confirming the mDuration semantics.
- **Sequence in/out == work area**: UXP `getInPoint/getOutPoint` on a
  Sequence are the work-area points (`MZ.InPoint/MZ.OutPoint`), matching py.
- **Constants**: `ppro.Constants` exposes `MarkerColor`, `InterpolationMode`,
  `VideoFieldType`, `PixelAspectRatio`, `ProjectItemColorLabel`, ... - these
  are candidate value-map sources for TODO section 1 WITHOUT setValue sweeps.
- **projectGuid == documentID** (`05259761...`), confirming documentID is the
  root project-item UID.

`export_dom.js` covers project, rootItem tree (with media paths),
sequences, tracks, clip items with full component chains (params, static
values, keyframe lists), transitions and markers (guid, colorIndex, url,
target). Component values match the ES exporter exactly on 06_api/07
(including the duplicate Blend Mode 18/0 pair), so UXP export can serve as
full ground truth for UXP-only fixtures. One gap, observed 26.3:
`getTrackItems(TrackItemType.TRANSITION)` returns null entries (inside and
outside `lockedAccess`) - the count is right but the item wrappers are
unimplemented, so transition DETAILS come from the stored XML only.
