/*
Reference for clip trim: shorten the V1 clip of the first sequence (new end
= start + 1s, source out pulled in accordingly), then save to `job.saveAs`.
Introspects the TrackItem wrapper for the trim API first. Diffing against
the source reveals every field Premiere touches for a timeline trim.
*/
module.exports.run = async function (job) {
    var ppro = require("premierepro");
    if (!job.saveAs) {
        throw new Error("job.saveAs is required");
    }
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
    var sequences = await project.getSequences();
    var track = await sequences[0].getVideoTrack(0);
    var clipType = ppro.Constants && ppro.Constants.TrackItemType
        ? ppro.Constants.TrackItemType.CLIP : 1;
    var items = await track.getTrackItems(clipType, false);
    if (!items.length) {
        throw new Error("V1 has no clips");
    }
    var item = items[0];

    var methods = [];
    var proto = item;
    while (proto) {
        Object.getOwnPropertyNames(proto).forEach(function (name) {
            if (/point|end|start|trim|move/i.test(name)
                && methods.indexOf(name) < 0) {
                methods.push(name);
            }
        });
        proto = Object.getPrototypeOf(proto);
    }

    var startTime = await item.getStartTime();
    var newEnd = ppro.TickTime.createWithTicks(
        String(Number(startTime.ticks) + 254016000000)
    );
    var how = null;
    var errors = [];
    var candidates = ["createSetEndAction", "createSetEndTimeAction"];
    for (var i = 0; i < candidates.length && !how; i += 1) {
        var method = candidates[i];
        if (typeof item[method] !== "function") {
            continue;
        }
        try {
            project.lockedAccess(function () {
                project.executeTransaction(function (compound) {
                    compound.addAction(item[method](newEnd));
                }, "py-premiere: trim clip");
            });
            how = method;
        } catch (e) {
            errors.push(method + ": " + String(e));
        }
    }

    var saved = null;
    if (how) {
        saved = await project.saveAs(job.saveAs);
    }
    return { methods: methods, how: how, errors: errors, saved: saved };
};
