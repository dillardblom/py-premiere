# Differences from ExtendScript

Intentional design choices where `py_premiere` diverges from the Premiere
Pro ExtendScript API. These are not bugs - they make the interface more
Pythonic or reflect that the package reads a file rather than driving a
running application.

## Naming conventions

ExtendScript uses `camelCase`; `py_premiere` uses `snake_case`:

| ExtendScript | py_premiere |
|---|---|
| `inPoint` | `in_point` |
| `mediaType` | `media_type` |
| `getColorByIndex()` | `color_index` (property) |
| `isMuted()` | `is_muted` |

No-argument getters (and their paired setters) become properties, even
where ExtendScript uses a method: `param.value`, `item.color_label`,
`marker.color_index = 1`. Only accessors that take an argument
(`param.get_value_at_key(time)`) or perform an imperative action
(`marker.set_type_as_web_link(url)`) stay methods.

## Indexing

ExtendScript collections are **1-based**; `py_premiere` uses **0-based**
Python lists:

=== "ExtendScript"

    ```javascript
    var firstTrack = sequence.videoTracks[0]; // already 0-based in PPro
    var firstClip = firstTrack.clips[0];
    ```

=== "py_premiere"

    ```python
    first_track = sequence.video_tracks[0]
    first_clip = first_track.clips[0]
    ```

`Track.index` is 0-based, so `sequence.video_tracks[track.index]` resolves
without offset arithmetic.

## Time is a single object

ExtendScript exposes times as ticks and seconds separately. `py_premiere`
returns a [`Time`](api/time.md) with both `ticks` (254016000000 per second)
and `seconds`:

```python
clip.start.ticks     # 1262874412800
clip.start.seconds   # 4.971633333333333
```

`Time` behaves as a value object: times compare, order, add and subtract,
scale by numbers, and convert to and from frame counts and `HH:MM:SS:FF`
timecode (including drop-frame, spelled with a `;` before the frame field):

```python
clip.end - clip.start                        # the duration as a Time
clip.start.to_timecode(sequence.timebase)    # "00:00:04:29"
Time.from_timecode("01:00:00;00", 8475667200)
```

## Collections iterate and look up by name

Model collections return a `NamedList`: a plain list that also accepts a
name as the index (first match wins, `KeyError` when absent). Containers
iterate directly, and `ProjectItem.walk()` yields every descendant:

```python
project.sequences["Seq A"]
clip.components["Motion"]["Position"].value
for clip in sequence.video_tracks["Video 1"]:
    ...
for item in project.root_item.walk():
    ...
```

ExtendScript has no equivalent; scripts scan the arrays by hand.

## `None` instead of sentinel values

Where ExtendScript reports a magic value for "not set", `py_premiere`
reports `None`:

| Surface | ExtendScript | py_premiere |
|---|---|---|
| in/out of an item with no media (root, bins) | `-400000` s | `None` |
| never-set sequence in/out point | `-400000` s | `None` |
| `getProxyPath` with no proxy | `0` | `None` |
| generator media path (`Black Video`, ...) | `""` | `None` |

Setting a sequence in/out point to `None` writes the sentinel, exactly as
Premiere does when the point is cleared.

## Filesystem paths are `pathlib.Path`

`media_path`, `proxy_path` and friends return `Path | None` rather than
strings; arguments accept `str` or `Path`. `tree_path` stays a string - it
is Premiere's virtual `\\root\\bin` notation, not a filesystem path.

## Byte-fidelity round-trip

`parse()` then `Project.save(path)` reproduces the original file **byte for
byte**. A file the serializer cannot reproduce exactly is refused at parse
time rather than silently rewritten, so a saved project is never a lossy
approximation of the input.

## Speed-adjusted source times are truncated

For a retimed clip, ExtendScript reports source in/out points as
`raw_ticks / playback_speed` **truncated** to an integer tick.
`py_premiere` reproduces that truncation exactly, and its `in_point` /
`out_point` setters pick the raw value that reads back to the requested
tick.

## Live names come from the master clip

A clip's name lives on its `MasterClip`; the `ProjectItem/Name` copy goes
stale when Premiere renames. `ProjectItem.name` and `TrackItem.name` follow
the live master-clip name, matching ExtendScript.
