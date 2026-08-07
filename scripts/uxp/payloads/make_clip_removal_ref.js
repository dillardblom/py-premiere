/*
Reference for timeline clip removal: remove the first clip from V1 of the
first sequence, then save to `job.saveAs`. Diffing against the source
reveals what Premiere detaches (the track item, its SubClip, and whether
the master clip/media survive).
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
    var track = await sequences[0].getVideoTrack(0);
    var clipType = ppro.Constants && ppro.Constants.TrackItemType
        ? ppro.Constants.TrackItemType.CLIP : 1;
    var probe = await track.getTrackItems(clipType, false);
    if (!probe.length) {
        throw new Error("V1 has no clips");
    }
    var mediaType = await probe[0].getMediaType();
    // DOM handles are only valid inside lockedAccess, so re-fetch the item
    // and build the selection + action there.
    var executed = null;
    project.lockedAccess(function () {
        var items = track.getTrackItems(clipType, false);
        var selection = null;
        ppro.TrackItemSelection.createEmptySelection(function (sel) {
            selection = sel;
        });
        selection.addItem(items[0], false);
        var action = editor.createRemoveItemsAction(
            selection, false, mediaType, false);
        executed = project.executeTransaction(function (compound) {
            compound.addAction(action);
        }, "py-premiere: remove clip");
    });
    var remaining = await track.getTrackItems(clipType, false);
    var saved = await project.saveAs(job.saveAs);
    return { executed: executed, remaining: remaining.length, saved: saved };
};
