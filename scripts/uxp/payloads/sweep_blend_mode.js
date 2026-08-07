/*
Blend Mode popup sweep on 05_features: the Opacity component carries TWO
"Blend Mode" params (a visible popup, ParameterID 2, XML default 18; and a
hidden twin, ParameterID 3, XML default 0). For each n set the FIRST param
and save `blend_a<n>.prproj`; then set the SECOND for a few values and save
`blend_b<n>.prproj`. Diffing the XML values reveals the coupling (internal
code vs popup index) and each param's accepted range. Also introspects the
param objects for any value-label API.
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
    var sequences = await project.getSequences();
    var track = await sequences[0].getVideoTrack(0);
    var clipType = ppro.Constants && ppro.Constants.TrackItemType
        ? ppro.Constants.TrackItemType.CLIP : 1;
    var items = await track.getTrackItems(clipType, false);
    var chain = await items[0].getComponentChain();
    var count = await chain.getComponentCount();
    var blend = [];
    for (var i = 0; i < count; i += 1) {
        var component = await chain.getComponentAtIndex(i);
        var params = await component.getParamCount();
        for (var p = 0; p < params; p += 1) {
            var param = await component.getParam(p);
            if (param.displayName === "Blend Mode") {
                blend.push(param);
            }
        }
    }
    if (blend.length < 2) {
        throw new Error("expected 2 Blend Mode params, found " + blend.length);
    }

    var methods = [];
    var proto = blend[0];
    while (proto) {
        Object.getOwnPropertyNames(proto).forEach(function (name) {
            if (methods.indexOf(name) < 0) {
                methods.push(name);
            }
        });
        proto = Object.getPrototypeOf(proto);
    }

    async function readBoth() {
        var a = await blend[0].getStartValue();
        var b = await blend[1].getStartValue();
        return [a.value, b.value];
    }

    async function setParam(param, n) {
        var error = null;
        project.lockedAccess(function () {
            try {
                project.executeTransaction(function (compound) {
                    var keyframe = param.createKeyframe(n);
                    compound.addAction(
                        param.createSetValueAction(keyframe, true)
                    );
                }, "py-premiere: sweep blend mode");
            } catch (e) {
                error = String(e);
            }
        });
        return error;
    }

    var results = { methods: methods, initial: await readBoth(), a: [], b: [] };

    for (var n = 0; n <= 27; n += 1) {
        var errA = await setParam(blend[0], n);
        var read = await readBoth();
        await project.saveAs(job.outDir + "/blend_a" + n + ".prproj");
        results.a.push({ set: n, read: read, error: errA });
    }
    var bValues = [0, 1, 2, 3, 5, 10, 18, 26, 31];
    for (var q = 0; q < bValues.length; q += 1) {
        var m = bValues[q];
        var errB = await setParam(blend[1], m);
        var readB = await readBoth();
        await project.saveAs(job.outDir + "/blend_b" + m + ".prproj");
        results.b.push({ set: m, read: readB, error: errB });
    }
    return results;
};
