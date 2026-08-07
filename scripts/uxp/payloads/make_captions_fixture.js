/*
Captions fixture: import `job.srtPath` into the open project (06_api),
probe the caption APIs (sequence/ppro-level), create a caption track from
the SRT if possible, then save to `job.saveAs`. Returns the introspection
so the working API gets documented either way.
*/
module.exports.run = async function (job) {
    var ppro = require("premierepro");
    if (!job.saveAs || !job.srtPath) {
        throw new Error("job.saveAs and job.srtPath are required");
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
    var sequence = sequences[0];

    function names(object, pattern) {
        var out = [];
        var proto = object;
        while (proto) {
            Object.getOwnPropertyNames(proto).forEach(function (name) {
                if (pattern.test(name) && out.indexOf(name) < 0) {
                    out.push(name);
                }
            });
            proto = Object.getPrototypeOf(proto);
        }
        return out;
    }

    var report = {
        pproCaption: names(ppro, /caption|transcript|text/i),
        sequenceCaption: names(sequence, /caption|track/i),
    };

    var imported = null;
    try {
        imported = await project.importFiles([job.srtPath]);
    } catch (e) {
        report.importError = String(e);
    }
    var root = await project.getRootItem();
    var items = await (ppro.FolderItem.cast(root)).getItems();
    var srtItem = null;
    report.items = [];
    for (var i = 0; i < items.length; i += 1) {
        report.items.push(items[i].name);
        if (items[i].name.indexOf(".srt") >= 0) {
            srtItem = items[i];
        }
    }

    if (srtItem && ppro.CaptionTrack
        && typeof ppro.CaptionTrack.createCaptionTrack === "function") {
        try {
            var result = await ppro.CaptionTrack.createCaptionTrack(
                project, srtItem, sequence
            );
            report.created = String(result);
        } catch (e2) {
            report.createError = String(e2);
        }
    } else if (srtItem) {
        report.captionTrackStatics = ppro.CaptionTrack
            ? names(ppro.CaptionTrack, /./) : null;
    }
    await project.saveAs(job.saveAs);
    report.saved = true;
    return report;
};
