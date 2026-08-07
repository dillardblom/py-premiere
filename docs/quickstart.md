# Quick Start

## Parse a project

```python
import py_premiere

app = py_premiere.parse("myproject.prproj")
project = app.project
print(project.name, project.path)
```

## Create a project from scratch

`new()` returns an empty project - byte-identical to one Premiere itself
creates - ready to edit and save:

```python
app = py_premiere.new()
app.project.root_item.add_bin("Footage")
app.project.save("fresh.prproj")
```

## Import media

`import_files` writes the same object graph Premiere's own import does,
using your machine's Premiere preferences for the still defaults:

```python
items = app.project.import_files(["logo.png", "voiceover.wav", "broll.mp4"])
sequence.video_tracks[0].add_clip(items[0])
```

Supported media:

| Kind  | Formats                                                            |
| ----- | ------------------------------------------------------------------ |
| Still | BMP, PNG, JPEG, GIF, TIFF, PSD                                     |
| Audio | WAV (16/24-bit PCM, 32-bit float, any channel count), AIFF, M4A, MP3, AAC, WMA |
| Video | AVI (uncompressed, MJPEG); H.264 (with or without AAC audio), H.265, ProRes, DNxHR in MP4/MOV; MPEG-2 in MXF |

Compressed audio is trimmed the way Premiere trims it. An MP3's encoder tag
states its priming and padding exactly - note ffmpeg signs that tag `Lavc`
rather than `LAME`, but writes the field in the same place - so the clip
comes out at its true length. A raw AAC stream has nowhere to declare a trim,
so nothing can recover its true length; Premiere drops exactly one frame of
decoder priming and py does the same, which leaves an AAC clip a fraction
long - Premiere's own answer has the same slack. Both were verified against
Premiere at four durations each.

Multi-channel audio follows Premiere's own rule: mono, stereo and 5.1 are
native channel types carried by one source clip, while any other channel
count is imported as one mono source clip per channel.

Media carrying a start timecode (a MOV timecode track, drop-frame or not)
reports it as `item.start_time`, and interlaced media keeps its native field
dominance. Each codec gets the exact `VideoStream` shape Premiere writes for
it, so importing a codec with no verified profile raises rather than
guessing.

## Walk the project panel

```python
def walk(item, depth=0):
    print("  " * depth + f"{item.name} [{item.type.name}]")
    for child in item.children:
        walk(child, depth + 1)

walk(project.root_item)

clip = project.root_item.children[0]
print(clip.media_path)
```

## Sequences, tracks and clips

```python
sequence = project.sequences[0]
print(sequence.frame_size)        # (1920, 1080)
print(sequence.timebase)          # ticks per frame (e.g. 10584000000 = 24 fps)

for track in sequence.video_tracks:
    for clip in track.clips:
        print(clip.name, clip.start.seconds, clip.end.seconds)
        print("source:", clip.in_point.seconds, "->", clip.out_point.seconds)
```

Times are `Time` objects: `ticks` (254016000000 per second) and `seconds`,
both read/write.

Each clip links back to its project-panel item and knows its playback
speed:

```python
clip = sequence.video_tracks[0].clips[0]
print(clip.speed, clip.is_speed_reversed)   # 1.0 False
print(clip.time_interpolation_type.name)     # FRAME_SAMPLING
item = clip.project_item                     # the source panel item
print(item.name, item.is_sequence)           # may differ from clip.name
print(track.is_muted)
```

## Components, parameters and keyframes

Only *materialized* components are stored - Premiere synthesizes untouched
intrinsics (Motion, Opacity, Volume) at runtime, so an unmodified clip
lists none.

```python
for component in clip.components:
    print(component.display_name, component.match_name)
    for param in component.properties:
        if param.is_time_varying():
            for key in param.keys:
                print(" ", key.seconds,
                      param.get_value_at_key(key),
                      param.get_interpolation_at_key(key),        # arriving
                      param.get_out_interpolation_at_key(key))    # leaving
        else:
            print(" ", param.display_name, "=", param.value)
        if param.color is not None:     # Color(r, g, b, a) for color params
            print(" ", param.display_name, param.color)
```

Scalar parameters are writable, and keyframes can be edited or added to a
static parameter (bezier tangents are computed to match Premiere's output):

```python
from py_premiere import Time
from py_premiere.enums import KeyframeInterpolation as Interp

param.value = 50                                  # static scalar
param.set_keyframes([                             # turns it time-varying
    (Time(1 * sequence.timebase), 0.0, Interp.LINEAR),
    (Time(20 * sequence.timebase), 100.0, Interp.BEZIER),
])
```

## Markers

```python
for marker in sequence.markers:
    print(marker.name, marker.type, marker.start.seconds)
    print(marker.color_index)                  # 0..7 palette index

marker = sequence.markers[0]
marker.comments = "reviewed"
marker.color_index = 1                          # red

# Create and delete markers (byte-identical to Premiere's own output)
new = sequence.add_marker("cue", py_premiere.Time(5 * sequence.timebase),
                          comments="scene 2", marker_type="Comment")
sequence.remove_marker(new)
```

## Muting and disabling

```python
track.is_muted = True           # a whole track
track.is_locked = True          # no edits allowed
track.is_sync_locked = False    # stops moving with the other tracks
clip.is_disabled = True         # a single clip
```

The two media types store a track mute in completely different places, and
py hides that: a **video** track keeps the flag on the track itself, while an
**audio** track keeps it on its mix-graph fader (Premiere ignores - and
deletes - a flag written on the track there). Both read and write through
the same `is_muted` property.

## Transitions

Transitions are read from the timeline (a surface ExtendScript never
exposed), audio crossfades included - they store the same way:

```python
for transition in track.transitions:
    print(transition.name, transition.match_name)
    print(transition.start.seconds, transition.end.seconds)
    print(transition.has_incoming_clip, transition.has_outgoing_clip)
    print(transition.cut_point.seconds)        # the edit it covers
    print(transition.border_width, transition.border_color)
    print(transition.is_reversed, transition.anti_alias_quality)
```

A transition can be put on either end of a clip and taken off again:

```python
transition = track.add_transition(clip, "ADBE Additive Dissolve")
track.add_transition(clip, "ADBE Additive Dissolve", at_start=False,
                     duration=py_premiere.Time(sequence.timebase * 30))
track.remove_transition(transition)
```

When a clip butts against the chosen end, the transition lands ON THE CUT
and covers both clips - and, like Premiere, it only takes the footage that
exists. The part before the cut plays the outgoing clip, so it cannot exceed
that clip nor the handle the INCOMING clip has before its in point; the part
after the cut is the mirror image. A clip with no handle takes no transition
on that side, so ask the returned transition what actually fitted:

```python
transition = track.add_transition(clip, "ADBE Additive Dissolve",
                                  at_start=False)
print(transition.duration.seconds, transition.cut_point_offset.seconds)
```

A transition whose
display name py has not read out of Premiere's own output must be named
explicitly (`name=`), since a match name does not imply one - `ADBE Additive
Dissolve` displays as `Additive Dissolve (Legacy)`.

How a transition is aligned follows from which of its two sides is real: a
head transition has only an incoming clip and sits entirely after the cut, a
tail one has only an outgoing clip and sits entirely before it, and one on a
cut has both and straddles it. `cut_point_offset` is how much of it falls
before the cut - Premiere clamps that to the handles the clips actually
have, so a cut transition is rarely split evenly.

## Work area, in/out and playhead

```python
sequence.work_area_in = py_premiere.Time(0)
sequence.work_area_out = py_premiere.Time(10 * sequence.timebase)
print(sequence.in_point.seconds, sequence.out_point.seconds)
print(sequence.playhead.seconds)
```

A sequence whose work area has never been touched stores a far-future
sentinel in `work_area_out`, so it covers everything.

The stored sequence settings are writable too (absent keys refuse rather
than guess their position):

```python
settings = sequence.settings
settings.max_bit_depth = True
settings.max_render_quality = True
settings.preview_frame_size = (1280, 720)
settings.preview_codec = 1634755432   # 'apch'
```

Premiere keeps a changed preview codec on open and recomputes the paired
`PreviewFormatIdentifier` itself.

## Captions

```python
for track in sequence.caption_tracks:
    for caption in track.captions:
        print(caption.text)
        print(caption.start.seconds, caption.end.seconds)          # timeline
        print(caption.source_start.seconds, caption.source_end.seconds)
```

The timeline times snap to whole frames; the source ones are what the
imported caption file stated. A caption's styling is not decoded.

SRT files import like any other media, producing the same object graph
Premiere's own import writes (cue times exact, text synthesized into
Premiere's styled-text payload), and land on a timeline caption track
exactly as `Sequence.createCaptionTrack` would build it:

```python
from py_premiere.enums import CaptionFormat

item = project.import_files(["subtitles.srt"])[0]
track = sequence.create_caption_track(item, CaptionFormat.CEA_708)
track.format = CaptionFormat.SUBTITLE   # or change it afterwards
track.captions[0].font_size = 75         # per-caption styling
track.captions[0].font_family = "Arial"
track.captions[0].text = "Rewritten"     # keeps the styling around it
```

The named style properties are all read/write: `font_size`,
`font_family`, `fill_color`, `stroke_color`, `stroke_width`,
`tracking`, `leading`, the shadow group (`shadow_color`,
`shadow_opacity`, `shadow_angle`, `shadow_distance`, `shadow_size`,
`shadow_blur`) and the background group (`background_color`,
`background_opacity`, `background_size`, `background_corner_radius`).
Reading one gives `None` when the caption stores nothing for it and
Premiere renders its default; setting it then ADDS the field (see
`CAMPAIGN.md` section 6b for what remains unnamed). Setting any stroke
or background property also switches that group's Appearance checkbox
on, so the stored values render.

## Text graphics

`add_graphic` synthesizes what Premiere's Type tool writes - infinite
synthetic media, a master outside the project panel, and a placement
carrying the `AE.ADBE Text` component:

```python
clip = sequence.video_tracks[0].add_graphic("Hello", position=(0.5, 0.25))

source_text = clip.components["Text"]["Source Text"]
print(source_text.text)                  # Hello
source_text.text = "Goodbye"             # re-text in place
source_text.font_family = "Arial"
clip.components["Text"]["Opacity"].value = 50
```

Both surfaces write the same `FormattedTextData` payload, so the text
splice is shared; styling beyond the font size is not decoded yet.

## Subclips and proxies

```python
if item.is_subclip:
    print(item.subclip_in_point, item.subclip_out_point)
    print(item.has_hard_boundaries)

second = py_premiere.Time(254016000000)
sub = item.create_sub_clip("intro cut", second, second * 3)
item.attach_proxy("proxies/clip_proxy.mp4")   # must match the frame aspect
```

A subclip's own `in_point`/`out_point` still span the whole file - the
boundaries are what narrow it. Both creations reproduce Premiere's own
object graphs (A/V media narrows both its streams); a proxy's stream
carries the hi-res frame rect as an override so the item keeps reporting
the original raster.

## Merged and multicam clips

Neither has a scripting API in Premiere itself; both synthesize the
hidden-sequence graphs its UI writes:

```python
video, audio = project.import_files(["cam.mp4", "lav.wav"])
merged = project.create_merged_clip(video, audio)    # "cam.mp4 - Merged"

wide, close = project.import_files(["wide.mp4", "close_av.mp4"])
multicam = project.create_multicam_clip([wide, close])
```

A merged clip keeps private copies of both sources; a multicam clip
plays the originals and files them into a `Processed Clips` bin. Scope
matches the verified fixtures: merged takes a video-only movie plus a
mono audio clip, multicam takes two or more movie angles of which
exactly one carries stereo audio (cameras sync at their starts).

## Generated media

Premiere's synthetic items carry a four-character code where a file path
would be, which is why they have no `media_path`:

```python
from py_premiere.enums import GeneratorType

for item in project.root_item.children:
    if item.generator_type is GeneratorType.COLOR_MATTE:
        print(item.name, item.generator_id)     # 'Color Matte' 'COLR'
```

An adjustment layer is backed by Black Video, so it reports
`BLACK_VIDEO` here and identifies itself through `is_adjustment_layer`.

## Motion Graphics templates

An MGT clip reads as an ordinary clip carrying a `Graphic Parameters`
component whose properties are the Essential Graphics controls. Their values
are text payloads rather than numbers:

```python
import json

for param in clip.components[0].properties:
    if param.text and param.text.startswith("{"):
        print(param.display_name, json.loads(param.text)["textEditValue"])
```

Importing a `.mogrt` places one on a video track, copying the template's
graphic next to the project the way Premiere does - so the project keeps
working without the archive:

```python
clip = sequence.import_mgt("Credit Text 01.mogrt", py_premiere.Time(0))
```

Like Premiere's own import this is an overwrite: it clears the clips the
template covers. Templates carrying audio are not supported.

## Edit the timeline

Clips can be placed, moved and removed; each edit produces the same object
graph Premiere writes:

```python
v1, v2 = sequence.video_tracks[0], sequence.video_tracks[1]
item = project.root_item.children[0]

clip = v2.add_clip(item, start=py_premiere.Time(0))   # place a project item
v2.move_clip(clip, v1, start=py_premiere.Time(sequence.timebase))
v1.remove_clip(clip)                                  # source stays in the panel
```

## Retiming

A time-remap curve maps timeline time to SOURCE seconds (rising across the
clip, not a speed percentage); py completes an unfinished curve with the
terminal key Premiere itself would append:

```python
second = py_premiere.Time(254016000000)
clip.set_time_remap([(py_premiere.Time(0), 0.0), (second, 2.0)])  # 2x
print(clip.time_remapping.keys)
clip.clear_time_remap()
```

## Modify and save

Read/write attributes validate their input and write through on `save`:

```python
sequence.name = "Main edit"
clip = sequence.video_tracks[0].clips[0]
clip.name = "Intro"
clip.end = py_premiere.Time(20 * sequence.timebase)

# Scalar effect parameters are writable (stored like Premiere's own output)
param = clip.components[0].properties[0]
if isinstance(param.value, float):
    param.value = 50

# Compositing blend mode - materializes the Opacity intrinsic on demand
from py_premiere.enums import BlendMode
clip.blend_mode = BlendMode.MULTIPLY

project.save("copy.prproj")       # atomic; refuses to overwrite
```

Read-only attributes (`project.name`, `sequence.timebase`, `track.id`, ...)
raise `AttributeError` on assignment, like their ExtendScript counterparts.

## Effect masks

A mask is itself a component, in one of two places depending on what it
masks:

```python
for component in clip.components:
    for mask in component.sub_components:        # masks ON an effect
        print(mask.match_name)                   # AE.ADBE AEMask2
        for param in mask.properties:
            print(" ", param.display_name, param.value)   # Feather, Opacity...

for mask in clip.selection_components:           # masks on the whole CLIP
    print(mask.match_name)
```

A mask's shape comes from `param.path` - a list of vertices with their
bezier handles, read/write. A default (undrawn) mask stores an EMPTY path
(its geometry is in the sibling Type/Scale/Rotation parameters); a drawn
mask stores its anchors, and py writes them the same way:

```python
from py_premiere.models.component import PathVertex

for vertex in mask["Path"].path or []:
    print(vertex.x, vertex.y, vertex.in_x, vertex.out_x)

mask["Path"].path = [
    PathVertex(0.5, 0.1, 0.5, 0.1, 0.5, 0.1, 1.0),
    PathVertex(0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 1.0),
    PathVertex(0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 1.0),
]
```

Both roles are creatable - Premiere's default mask, adjustable through the
returned component's parameters (drawn pen paths are not synthesizable
yet):

```python
mask = component.add_mask()          # attach to this effect
mask["Feather"].value = 30
mask["Position"].value = [0.25, 0.75]

clip_mask = clip.add_mask()          # mask the clip as a whole
```

## Export to FCPXML

```python
from py_premiere.export import export_fcpxml

export_fcpxml(project, "edit.fcpxml")                    # first sequence
export_fcpxml(project, "b.fcpxml", project.sequences[1])
```

The first video track becomes the spine (with gaps over the holes) and every
other track's clips become connected clips on lanes. Times stay exact -
29.97 is written `1001/30000s`, never a rounded decimal. A clip that cannot
be placed raises rather than being silently dropped.

## Byte fidelity

`parse` then `save` with no modification reproduces the original file byte
for byte. Files containing constructs the serializer cannot faithfully
reproduce are refused at parse time with a `ValueError` - never silently
rewritten.

## Build a project from scratch

Every piece composes - no Premiere required:

```python
app = py_premiere.new()
sequence = app.project.add_sequence("Built by py")
clips = app.project.import_files(["logo.png", "voiceover.wav", "broll.avi"])
sequence.video_tracks[0].add_clip(clips[2])
sequence.audio_tracks[0].add_clip(clips[1])
sequence.add_marker("start here", py_premiere.Time(0))
app.project.save("built.prproj")
```

## Footage interpretation

```python
from py_premiere.enums import AlphaUsage, VideoFieldType

item = project.root_item.children[0]
interp = item.footage_interpretation      # None for bins / audio-only
print(interp.alpha_usage, interp.field_type, interp.pixel_aspect_ratio)

interp.alpha_usage = AlphaUsage.PREMULTIPLIED   # read/write
interp.field_type = VideoFieldType.UPPER_FIRST
interp.frame_rate = py_premiere.Time(20321280000)   # ticks/frame (12.5 fps)
interp.pixel_aspect_ratio = (40, 33)                # the stored pair
interp.frame_rate = None                            # back to the native rate

item.scale_to_frame_size = True   # placements scale to the sequence frame
```

A frame-rate override also rewrites the media source's duration to the
same frame count at the new rate, exactly as Premiere's own override does.

## Sequence presets

```python
print(project.sequence_presets())         # 1080p, 4K, HDR, social, broadcast
project.add_sequence("Broadcast", preset="1080p2997")
project.add_sequence("Graded", preset="2160p2997hdr")
project.add_sequence("Layered", video_tracks=8)   # presets all ask for 3
```

Both the empty project and a new sequence are built from scratch rather than
copied from a bundled file, so each one gets its own identifiers and carries
nothing from the machine that captured a skeleton. The presets cover 1080p at
23.976/25/29.97/50/59.94, 4K at 23.976/25/29.97/50/59.94 in SDR and BT.2100
HLG, the square and portrait social sizes, and the broadcast presets whose
tracks are discrete mono channels
rather than stereo - every value taken from a sequence Premiere made from the
matching preset.
