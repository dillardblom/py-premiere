/*
Reference for bin creation: create a bin in the project root, then save to
`job.saveAs`. Diffing against the source reveals the wiring Premiere
synthesizes for a new bin (BinProjectItem + ProjectItemContainer + the
parent's item list entry + NextID).
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
    var executed = null;
    project.lockedAccess(function () {
        var action = root.createBinAction("py-bin", true);
        executed = project.executeTransaction(function (compound) {
            compound.addAction(action);
        }, "py-premiere: create bin");
    });
    var items = await root.getItems();
    var names = [];
    for (var i = 0; i < items.length; i += 1) {
        names.push(items[i].name);
    }
    var saved = await project.saveAs(job.saveAs);
    return { executed: executed, rootItems: names, saved: saved };
};
