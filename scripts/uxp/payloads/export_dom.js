/*
Export the UXP DOM view of the active project as JSON.

Ground-truth source for fixtures ExtendScript cannot describe
(transitions, keyframe interpolation, ...). Covers project, rootItem tree,
sequences (settings/points), tracks, clip items with component chains,
transitions, and sequence markers. Field failures are recorded per-object
under `_errors` instead of aborting the export.

Transition track items are only usable inside `project.lockedAccess` -
outside it `getTrackItems(TRANSITION)` yields null entries (observed 26.3).
*/

function tick(value) {
    if (value === null || value === undefined) {
        return null;
    }
    var out = {};
    try {
        out.seconds = value.seconds;
    } catch (error) {
        out.secondsError = String(error);
    }
    try {
        out.ticks = value.ticks;
    } catch (error) {
        out.ticksError = String(error);
    }
    try {
        out.ticksNumber = value.ticksNumber;
    } catch (error) {
        out.ticksNumberError = String(error);
    }
    return out;
}

async function grab(target, label, fn) {
    try {
        target[label] = await fn();
    } catch (error) {
        if (!target._errors) {
            target._errors = {};
        }
        target._errors[label] = (error && error.message) || String(error);
    }
}

function plainValue(value) {
    if (value === null || value === undefined) {
        return null;
    }
    if (typeof value === "object") {
        // Keyframe-ish wrappers carry the payload in `.value`; PointF has
        // x/y; TickTime has ticks.
        if (value.value !== undefined) {
            return plainValue(value.value);
        }
        if (value.ticksNumber !== undefined) {
            return tick(value);
        }
        if (value.x !== undefined && value.y !== undefined) {
            return { x: value.x, y: value.y };
        }
        if (value.red !== undefined && value.green !== undefined
            && value.blue !== undefined) {
            return {
                red: value.red, green: value.green,
                blue: value.blue, alpha: value.alpha,
            };
        }
        return String(value);
    }
    return value;
}

async function exportParam(param) {
    var out = {};
    await grab(out, "displayName", function () { return param.displayName; });
    await grab(out, "isTimeVarying", function () {
        return param.isTimeVarying();
    });
    await grab(out, "value", async function () {
        return plainValue(await param.getStartValue());
    });
    if (out.isTimeVarying) {
        await grab(out, "keyframes", async function () {
            var times = await param.getKeyframeListAsTickTimes();
            var keys = [];
            for (var i = 0; i < times.length; i += 1) {
                var entry = { time: tick(times[i]) };
                await grab(entry, "value", async function () {
                    return plainValue(await param.getValueAtTime(times[i]));
                });
                keys.push(entry);
            }
            return keys;
        });
    }
    return out;
}

async function exportComponents(item) {
    var chain = await item.getComponentChain();
    if (!chain) {
        return null;
    }
    var count = await chain.getComponentCount();
    var components = [];
    for (var i = 0; i < count; i += 1) {
        var component = await chain.getComponentAtIndex(i);
        var out = {};
        await grab(out, "displayName", function () {
            return component.getDisplayName();
        });
        await grab(out, "matchName", function () {
            return component.getMatchName();
        });
        await grab(out, "params", async function () {
            var paramCount = await component.getParamCount();
            var params = [];
            for (var j = 0; j < paramCount; j += 1) {
                params.push(await exportParam(await component.getParam(j)));
            }
            return params;
        });
        components.push(out);
    }
    return components;
}

async function exportTrackItem(item) {
    var out = {};
    await grab(out, "name", function () { return item.getName(); });
    await grab(out, "start", async function () {
        return tick(await item.getStartTime());
    });
    await grab(out, "end", async function () {
        return tick(await item.getEndTime());
    });
    await grab(out, "inPoint", async function () {
        return tick(await item.getInPoint());
    });
    await grab(out, "outPoint", async function () {
        return tick(await item.getOutPoint());
    });
    await grab(out, "duration", async function () {
        return tick(await item.getDuration());
    });
    await grab(out, "speed", function () { return item.getSpeed(); });
    await grab(out, "isSpeedReversed", function () {
        return item.isSpeedReversed();
    });
    await grab(out, "disabled", function () { return item.isDisabled(); });
    await grab(out, "isAdjustmentLayer", function () {
        return item.isAdjustmentLayer();
    });
    await grab(out, "type", function () { return item.getType(); });
    await grab(out, "mediaType", async function () {
        return String(await item.getMediaType());
    });
    await grab(out, "projectItemName", async function () {
        var projectItem = await item.getProjectItem();
        return projectItem ? projectItem.name : null;
    });
    await grab(out, "components", function () {
        return exportComponents(item);
    });
    return out;
}

async function exportTransitions(project, track, transitionType) {
    // Handles are only valid inside lockedAccess; the getters return
    // promises that stay resolvable after the block ends.
    var pending = [];
    project.lockedAccess(function () {
        var items = track.getTrackItems(transitionType, false);
        for (var i = 0; i < items.length; i += 1) {
            var item = items[i];
            if (!item) {
                pending.push({ _errors: { item: "null entry" } });
                continue;
            }
            pending.push({
                name: item.getName(),
                start: item.getStartTime(),
                end: item.getEndTime(),
            });
        }
    });
    var out = [];
    for (var i = 0; i < pending.length; i += 1) {
        var raw = pending[i];
        if (raw._errors) {
            out.push(raw);
            continue;
        }
        var entry = {};
        await grab(entry, "name", function () { return raw.name; });
        await grab(entry, "start", async function () {
            return tick(await raw.start);
        });
        await grab(entry, "end", async function () {
            return tick(await raw.end);
        });
        out.push(entry);
    }
    return out;
}

async function exportTrack(project, track, ppro) {
    var out = {};
    await grab(out, "name", function () { return track.name; });
    await grab(out, "id", function () { return track.id; });
    await grab(out, "index", function () { return track.getIndex(); });
    await grab(out, "muted", function () { return track.isMuted(); });
    var clipType = ppro.Constants && ppro.Constants.TrackItemType
        ? ppro.Constants.TrackItemType.CLIP : 1;
    var transitionType = ppro.Constants && ppro.Constants.TrackItemType
        ? ppro.Constants.TrackItemType.TRANSITION : 2;
    await grab(out, "clips", async function () {
        var items = await track.getTrackItems(clipType, false);
        var clips = [];
        for (var i = 0; i < items.length; i += 1) {
            clips.push(await exportTrackItem(items[i]));
        }
        return clips;
    });
    await grab(out, "transitions", function () {
        return exportTransitions(project, track, transitionType);
    });
    return out;
}

async function exportMarkers(ppro, sequence) {
    var markersObject = await ppro.Markers.getMarkers(sequence);
    var markers = await markersObject.getMarkers();
    var out = [];
    for (var i = 0; i < markers.length; i += 1) {
        var marker = markers[i];
        var entry = {};
        await grab(entry, "guid", function () { return String(marker.guid); });
        await grab(entry, "name", function () { return marker.getName(); });
        await grab(entry, "comments", function () {
            return marker.getComments();
        });
        await grab(entry, "start", async function () {
            return tick(await marker.getStart());
        });
        await grab(entry, "duration", async function () {
            return tick(await marker.getDuration());
        });
        await grab(entry, "type", function () { return marker.getType(); });
        await grab(entry, "colorIndex", function () {
            return marker.getColorIndex();
        });
        await grab(entry, "url", function () { return marker.getUrl(); });
        await grab(entry, "target", function () { return marker.getTarget(); });
        out.push(entry);
    }
    return out;
}

async function exportProjectItem(ppro, item) {
    var out = {};
    await grab(out, "name", function () { return item.name; });
    await grab(out, "type", function () { return item.type; });
    await grab(out, "colorLabel", function () { return item.getColorLabelIndex(); });
    await grab(out, "markers", function () {
        // getMarkers needs the ClipProjectItem cast; the raw wrapper
        // silently yields an empty list.
        var cast = ppro.ClipProjectItem.cast(item);
        return exportMarkers(ppro, cast || item);
    });
    await grab(out, "mediaPath", async function () {
        var clip = ppro.ClipProjectItem.cast(item);
        return clip ? await clip.getMediaFilePath() : null;
    });
    var folder = null;
    try {
        folder = ppro.FolderItem.cast(item);
    } catch (ignored) {
        // Not a folder.
    }
    if (folder) {
        await grab(out, "children", async function () {
            var children = await folder.getItems();
            var result = [];
            for (var i = 0; i < children.length; i += 1) {
                result.push(await exportProjectItem(ppro, children[i]));
            }
            return result;
        });
    }
    return out;
}

async function exportSequence(ppro, project, sequence) {
    var out = {};
    await grab(out, "name", function () { return sequence.name; });
    await grab(out, "guid", function () { return String(sequence.guid); });
    await grab(out, "timebase", function () {
        return sequence.getTimebase();
    });
    await grab(out, "frameSize", async function () {
        var size = await sequence.getFrameSize();
        return { width: size.width, height: size.height };
    });
    await grab(out, "inPoint", async function () {
        return tick(await sequence.getInPoint());
    });
    await grab(out, "outPoint", async function () {
        return tick(await sequence.getOutPoint());
    });
    await grab(out, "zeroPoint", async function () {
        return tick(await sequence.getZeroPoint());
    });
    await grab(out, "end", async function () {
        return tick(await sequence.getEndTime());
    });
    await grab(out, "markers", function () {
        return exportMarkers(ppro, sequence);
    });
    await grab(out, "videoTracks", async function () {
        var count = await sequence.getVideoTrackCount();
        var tracks = [];
        for (var i = 0; i < count; i += 1) {
            tracks.push(await exportTrack(
                project, await sequence.getVideoTrack(i), ppro));
        }
        return tracks;
    });
    await grab(out, "audioTracks", async function () {
        var count = await sequence.getAudioTrackCount();
        var tracks = [];
        for (var i = 0; i < count; i += 1) {
            tracks.push(await exportTrack(
                project, await sequence.getAudioTrack(i), ppro));
        }
        return tracks;
    });
    return out;
}

module.exports.run = async function (job) {
    var ppro = require("premierepro");
    // The runner opens the project at launch, but the plugin loads while
    // Premiere is still booting - poll until the project is up.
    // (Project.open from the Home screen hangs in 26.3; don't rely on it.)
    var project = null;
    for (var attempt = 0; attempt < 45 && !project; attempt += 1) {
        project = await ppro.Project.getActiveProject();
        if (!project) {
            await new Promise(function (resolve) {
                setTimeout(resolve, 2000);
            });
        }
    }
    if (!project) {
        throw new Error("no active project after 90s");
    }
    var out = {};
    await grab(out, "projectName", function () { return project.name; });
    await grab(out, "projectPath", function () { return project.path; });
    await grab(out, "projectGuid", function () {
        return String(project.guid);
    });
    await grab(out, "rootItem", async function () {
        return exportProjectItem(ppro, await project.getRootItem());
    });
    await grab(out, "sequences", async function () {
        var sequences = await project.getSequences();
        var result = [];
        for (var i = 0; i < sequences.length; i += 1) {
            result.push(await exportSequence(ppro, project, sequences[i]));
        }
        return result;
    });
    return out;
};
