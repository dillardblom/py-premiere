/*
Disable the first V1 clip via createSetDisabledAction, then save to
`job.saveAs`. Diffing against the source reveals the disabled flag's XML
home (elided when the clip is enabled).
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
    var executed = null;
    project.lockedAccess(function () {
        var action = items[0].createSetDisabledAction(true);
        executed = project.executeTransaction(function (compound) {
            compound.addAction(action);
        }, "py-premiere: disable clip");
    });
    var disabled = await items[0].isDisabled();
    var saved = await project.saveAs(job.saveAs);
    return { executed: executed, disabled: disabled, saved: saved };
};
