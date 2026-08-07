/*
Reference for clip insertion: overwrite the bmp project item onto V2 of the
first sequence at t=0, then save to `job.saveAs`. Diffing against the source
reveals the full graph Premiere synthesizes (TrackItem + component chain +
SubClip + Clip) for a clip placed from a project item.
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
    var items = await root.getItems();
    var source = null;
    for (var i = 0; i < items.length; i += 1) {
        if (items[i].name === "red_64x36.bmp") {
            source = items[i];
            break;
        }
    }
    if (!source) {
        throw new Error("no red_64x36.bmp project item");
    }
    var zero = ppro.TickTime.createWithTicks("0");
    var executed = null;
    project.lockedAccess(function () {
        // Place on V2 (video track index 1), no audio track.
        var action = editor.createOverwriteItemAction(source, zero, 1, -1);
        executed = project.executeTransaction(function (compound) {
            compound.addAction(action);
        }, "py-premiere: insert clip");
    });
    var track = await sequences[0].getVideoTrack(1);
    var clipType = ppro.Constants && ppro.Constants.TrackItemType
        ? ppro.Constants.TrackItemType.CLIP : 1;
    var placed = await track.getTrackItems(clipType, false);
    var saved = await project.saveAs(job.saveAs);
    return { executed: executed, placed: placed.length, saved: saved };
};
