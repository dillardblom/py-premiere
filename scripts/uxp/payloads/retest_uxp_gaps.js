/*
CAMPAIGN section 5 retests, one UXP launch on 06_api:
1. createSubClipAction with the DOCUMENTED signature - the 2026-07-22
   probe never tried the fifth argument as an options object
   ({takeVideo, takeAudio}), which the reference says it is.
2. The audio keyframe write that did not persist in the earlier attempt:
   introspect the Level param's action factories and try them, then save
   so persistence can be checked from the file.
Saves uxp_retest.prproj into job.outDir.
*/
module.exports.run = async function (job) {
    var ppro = require("premierepro");
    if (!job.outDir || !job.avPath) {
        throw new Error("job.outDir and job.avPath are required");
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
    var report = { subclip: {}, audioKeys: {} };

    // --- 1. createSubClipAction with the options object --------------------
    try {
        await project.importFiles([job.avPath]);
        var root = await project.getRootItem();
        var items = await (ppro.FolderItem.cast(root)).getItems();
        var av = null;
        for (var i = 0; i < items.length; i += 1) {
            if (items[i].name.indexOf("bars_64x36_av") >= 0) {
                av = ppro.ClipProjectItem.cast(items[i]);
            }
        }
        if (!av) {
            throw new Error("A/V item not found after import");
        }
        var start = ppro.TickTime.createWithTicks("63504000000");
        var end = ppro.TickTime.createWithTicks("190512000000");
        var shapes = [
            ["options object", function () {
                return av.createSubClipAction("uxp subclip", start, end, false,
                    { takeVideo: true, takeAudio: true });
            }],
            ["no fifth arg", function () {
                return av.createSubClipAction("uxp subclip", start, end, false);
            }]
        ];
        report.subclip.tried = [];
        for (var s = 0; s < shapes.length && !report.subclip.ok; s += 1) {
            try {
                var make = shapes[s][1];
                // The action FACTORY itself requires locked access, not
                // just the transaction (first retest failed on exactly
                // that).
                project.lockedAccess(function () {
                    var action = make();
                    project.executeTransaction(function (compound) {
                        compound.addAction(action);
                    }, "py-premiere: uxp subclip");
                });
                report.subclip.tried.push({ shape: shapes[s][0], result: "executed" });
                report.subclip.ok = shapes[s][0];
            } catch (eShape) {
                report.subclip.tried.push({
                    shape: shapes[s][0], error: String(eShape)
                });
            }
        }
    } catch (eSub) {
        report.subclip.error = String(eSub);
    }

    // --- 2. audio keyframe write --------------------------------------------
    try {
        var sequences = await project.getSequences();
        var sequence = sequences[0];
        var audioTrack = await sequence.getAudioTrack(0);
        var trackItems = await audioTrack.getTrackItems(
            ppro.Constants.TrackItemType.CLIP, false);
        var clip = trackItems[0];
        var chain = await clip.getComponentChain();
        var level = null;
        var names = [];
        for (var c = 0; c < await chain.getComponentCount(); c += 1) {
            var component = await chain.getComponentAtIndex(c);
            for (var p = 0; p < await component.getParamCount(); p += 1) {
                var param = await component.getParam(p);
                names.push(String(param.displayName));
                if (String(param.displayName) === "Level") {
                    level = param;
                }
            }
        }
        report.audioKeys.params = names;
        if (!level) {
            throw new Error("no Level param on the audio clip");
        }
        var factories = [];
        var proto = level;
        while (proto) {
            Object.getOwnPropertyNames(proto).forEach(function (name) {
                if (/keyframe|timevarying|value/i.test(name)
                        && factories.indexOf(name) < 0) {
                    factories.push(name);
                }
            });
            proto = Object.getPrototypeOf(proto);
        }
        factories.sort();
        report.audioKeys.factories = factories;

        var one = ppro.TickTime.createWithTicks("254016000000");
        var keyframe = await level.createKeyframe(0.25);
        project.lockedAccess(function () {
            project.executeTransaction(function (compound) {
                compound.addAction(level.createSetTimeVaryingAction(true));
                compound.addAction(level.createAddKeyframeAction(keyframe, one));
            }, "py-premiere: audio keyframe");
        });
        report.audioKeys.executed = true;
    } catch (eKeys) {
        report.audioKeys.error = String(eKeys);
    }

    await project.saveAs(job.outDir + "/uxp_retest.prproj");
    return report;
};
