# CLI Tools

Installed with the package (`uv sync --extra dev` in a checkout, or
`pip install py-premiere`). Every tool supports `--help`.

## pr-inspect

Single-file structure inspection.

```sh
pr-inspect file.prproj                 # object summary (counts by tag)
pr-inspect file.prproj --list          # top-level objects with IDs and names
pr-inspect file.prproj --tree --depth 3
pr-inspect file.prproj --dump 42       # one object's XML by ObjectID/UID/tag
pr-inspect file.prproj --xml --out payload.xml
```

Use `--out` for byte-exact payload extraction; PowerShell's `>` redirection
re-encodes output.

## pr-compare

Structural diff between two projects, aware of resave churn: objects are
matched by `ObjectUID`, then by an ObjectID-insensitive signature, and
`ObjectRef` values are compared through their resolved target.

```sh
pr-compare with_feature.prproj without_feature.prproj
pr-compare a.prproj b.prproj --filter Sequence
pr-compare a.prproj b.prproj --show-churn
```

Exit code 0 means no differences beyond renumbering churn. This is the main
reverse-engineering tool: compare two projects that differ in a single
Premiere setting to locate the field.

## pr-visualize

Tree view of the parsed object model: project panel plus every sequence with
tracks and clips.

```sh
pr-visualize file.prproj
pr-visualize file.prproj --items
pr-visualize file.prproj --sequences
```

## pr-validate

Compares parsed output against ExtendScript ground truth (`<file>.json`
exported by `scripts/jsx/export_project_json.jsx` from inside Premiere).

```sh
pr-validate file.prproj
pr-validate file.prproj --json ground_truth.json
pr-validate a.prproj b.prproj c.prproj
```

`--coverage` additionally lists the ground-truth keys the run never
asserted, so a field that is silently ignored cannot masquerade as a passing
check; `--report-json PATH` writes the same information (status, mismatches,
asserted and ignored keys per file) as machine-readable JSON.

```sh
pr-validate file.prproj --coverage
pr-validate a.prproj b.prproj --report-json report.json
```
