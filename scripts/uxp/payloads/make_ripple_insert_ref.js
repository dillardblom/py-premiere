/*
Reference for ripple insert: INSERT (not overwrite) the bmp project item
onto V1 of the first sequence at t=0, then save to `job.saveAs`. Diffing
against the source reveals how Premiere shifts the existing clips (which
tracks ripple, and what the placed graph looks like).
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
    var editor = await ppro.SequenceEditor.getEditor(sequences[0]);
    var root = await project.getRootItem();
    var items = await (ppro.FolderItem.cast(root)).getItems();
    var source = null;
    for (var i = 0; i < items.length; i += 1) {
        if (items[i].name === "red_64x36.bmp") {
            source = items[i];
        }
    }
    if (!source) {
        throw new Error("no red_64x36.bmp item");
    }

    var methods = [];
    var proto = editor;
    while (proto) {
        Object.getOwnPropertyNames(proto).forEach(function (name) {
            if (/insert|overwrite/i.test(name) && methods.indexOf(name) < 0) {
                methods.push(name);
            }
        });
        proto = Object.getPrototypeOf(proto);
    }

    var zero = ppro.TickTime.createWithTicks("0");
    var error = null;
    try {
        project.lockedAccess(function () {
            // (item, time, videoTrackIndex, audioTrackIndex, limitShift)
            var action = editor.createInsertProjectItemAction(
                source, zero, 0, -1, false
            );
            project.executeTransaction(function (compound) {
                compound.addAction(action);
            }, "py-premiere: ripple insert");
        });
    } catch (e) {
        error = String(e);
    }
    var saved = null;
    if (!error) {
        saved = await project.saveAs(job.saveAs);
    }
    return { methods: methods, error: error, saved: saved };
};
