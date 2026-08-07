/*
Multi-mask numbering evidence: introspect ObjectMaskUtils and try to put
TWO masks on one effect (and two clip-level masks on another clip), then
save 75_two_masks so the numbering scheme (InstanceName / ID /
NextComponentNumber) can be read off the file.
*/
module.exports.run = async function (job) {
    var ppro = require("premierepro");
    if (!job.outDir) {
        throw new Error("job.outDir is required");
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
    var report = { utils: {}, steps: {} };

    function names(obj) {
        var out = [];
        var proto = obj;
        while (proto) {
            Object.getOwnPropertyNames(proto).forEach(function (name) {
                if (out.indexOf(name) < 0) {
                    out.push(name);
                }
            });
            proto = Object.getPrototypeOf(proto);
        }
        out.sort();
        return out;
    }
    try {
        report.utils.objectMaskUtils = ppro.ObjectMaskUtils
            ? names(ppro.ObjectMaskUtils) : "absent";
    } catch (eU) {
        report.utils.error = String(eU);
    }

    try {
        var sequences = await project.getSequences();
        var sequence = sequences[1] || sequences[0];
        var track = await sequence.getVideoTrack(0);
        var items = await track.getTrackItems(
            ppro.Constants.TrackItemType.CLIP, false);
        var clip = items[0];
        var chain = await clip.getComponentChain();
        var blur = null;
        for (var c = 0; c < await chain.getComponentCount(); c += 1) {
            var component = await chain.getComponentAtIndex(c);
            var matchName = "";
            try {
                matchName = String(await component.getMatchName());
            } catch (eM) {
                matchName = String(component.matchName || "");
            }
            report.steps["component" + c] = matchName;
            if (/Blur/i.test(matchName)) {
                blur = component;
            }
        }
        report.steps.blurFound = blur !== null;
        if (blur && ppro.ObjectMaskUtils) {
            var shapes = [
                ["addMaskToComponent", function () {
                    return ppro.ObjectMaskUtils.addMaskToComponent(blur);
                }],
                ["createMaskAction", function () {
                    return ppro.ObjectMaskUtils.createMaskAction(blur);
                }]
            ];
            report.steps.tried = [];
            for (var s = 0; s < shapes.length; s += 1) {
                try {
                    var make = shapes[s][1];
                    var outcome = null;
                    project.lockedAccess(function () {
                        outcome = make();
                        if (outcome && outcome.constructor
                                && /Action/.test(String(outcome.constructor.name))) {
                            project.executeTransaction(function (compound) {
                                compound.addAction(outcome);
                            }, "py-premiere: mask " + s);
                        }
                    });
                    report.steps.tried.push({
                        shape: shapes[s][0], result: String(outcome)
                    });
                } catch (eShape) {
                    report.steps.tried.push({
                        shape: shapes[s][0], error: String(eShape)
                    });
                }
            }
        }
        await project.saveAs(job.outDir + "/75_two_masks.prproj");
        report.steps.saved = true;
    } catch (eMain) {
        report.steps.error = String(eMain);
    }
    return report;
};
