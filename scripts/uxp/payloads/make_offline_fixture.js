/*
Set the bmp project item offline via createSetOfflineAction, then save to
`job.saveAs`. Diffing against the source reveals the offline flag's XML home.
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
    var root = await project.getRootItem();
    var items = await (ppro.FolderItem.cast(root)).getItems();
    var clip = null;
    for (var i = 0; i < items.length; i += 1) {
        if (items[i].name === "red_64x36.bmp") {
            clip = ppro.ClipProjectItem.cast(items[i]);
        }
    }
    if (!clip) {
        throw new Error("no red_64x36.bmp clip item");
    }
    var error = null;
    try {
        project.lockedAccess(function () {
            var action = clip.createSetOfflineAction();
            project.executeTransaction(function (compound) {
                compound.addAction(action);
            }, "py-premiere: set offline");
        });
    } catch (e) {
        error = String(e);
    }
    var offline = null;
    try {
        offline = await clip.isOffline();
    } catch (e2) {
        offline = "ERR " + String(e2);
    }
    var saved = await project.saveAs(job.saveAs);
    return { error: error, offline: offline, saved: saved };
};
