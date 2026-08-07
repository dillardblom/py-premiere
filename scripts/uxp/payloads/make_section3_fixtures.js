/*
Section-3 fixtures (CAMPAIGN.md): frame-rate override, PAR override and
scale-to-frame-size - one action per ITEM so consecutive pr-compare diffs
isolate every field. Saves the base into job.refDir and the three fixtures
into job.outDir (the committed corpus dir).
*/
module.exports.run = async function (job) {
    var ppro = require("premierepro");
    if (!job.outDir || !job.refDir || !job.assetsDir) {
        throw new Error("job.outDir, job.refDir and job.assetsDir are required");
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
    await project.importFiles([
        job.assetsDir + "/bars_64x36_h264.mp4",
        job.assetsDir + "/bars_64x36_prores.mov"
    ]);
    var root = await project.getRootItem();
    var items = await (ppro.FolderItem.cast(root)).getItems();
    function find(fragment) {
        for (var i = 0; i < items.length; i += 1) {
            if (items[i].name.indexOf(fragment) >= 0) {
                return ppro.ClipProjectItem.cast(items[i]);
            }
        }
        throw new Error("no item matching " + fragment);
    }
    var h264 = find("h264");
    var prores = find("prores");
    var still = find("red_64x36");
    await project.saveAs(job.refDir + "/s3_base.prproj");

    // What the 26.3 item actually reflects, in case the documented action
    // names have drifted.
    var methods = [];
    var proto = h264;
    while (proto) {
        Object.getOwnPropertyNames(proto).forEach(function (name) {
            if (/override|scale/i.test(name) && methods.indexOf(name) < 0) {
                methods.push(name);
            }
        });
        proto = Object.getPrototypeOf(proto);
    }

    function act(clip, make, label) {
        project.lockedAccess(function () {
            var action = make(clip);
            project.executeTransaction(function (compound) {
                compound.addAction(action);
            }, "py-premiere: " + label);
        });
    }

    var report = { methods: methods, steps: {} };
    try {
        act(h264, function (c) {
            return c.createSetOverrideFrameRateAction(12.5);
        }, "rate override");
        await project.saveAs(job.outDir + "/68_rate_override.prproj");
        report.steps.rate = "saved";
    } catch (eRate) {
        report.steps.rate = String(eRate);
    }
    try {
        act(prores, function (c) {
            return c.createSetOverridePixelAspectRatioAction(40, 33);
        }, "par override");
        await project.saveAs(job.outDir + "/69_par_override.prproj");
        report.steps.par = "saved";
    } catch (ePar) {
        report.steps.par = String(ePar);
    }
    try {
        act(still, function (c) {
            return c.createSetScaleToFrameSizeAction();
        }, "scale to frame");
        await project.saveAs(job.outDir + "/70_scale_to_frame.prproj");
        report.steps.scale = "saved";
    } catch (eScale) {
        report.steps.scale = String(eScale);
    }
    return report;
};
