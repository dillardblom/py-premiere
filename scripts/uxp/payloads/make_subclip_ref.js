/*
Create a subclip of the bmp project item and save to `job.saveAs`. Tries a
few createSubClipAction signatures (name, start, end, ...) and reports which
worked; the diff against the source reveals the subclip's object graph.
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
        if (items[i].name === "renamed tone") {
            clip = ppro.ClipProjectItem.cast(items[i]);
        }
    }
    if (!clip) {
        throw new Error("no wav clip item");
    }

    var start = ppro.TickTime.createWithSeconds(0.1);
    var end = ppro.TickTime.createWithSeconds(0.5);
    var attempts = [
        function () {
            return clip.createSubClipAction("sub", start, end, true, true, true);
        },
        function () {
            return clip.createSubClipAction("sub", 0.1, 0.5, true, true, true);
        },
        function () {
            return clip.createSubClipAction("sub", start, end, 1, 1, 1);
        },
    ];
    var how = null;
    var errors = [];
    for (var a = 0; a < attempts.length && !how; a += 1) {
        try {
            project.lockedAccess(function () {
                var action = attempts[a]();
                project.executeTransaction(function (compound) {
                    compound.addAction(action);
                }, "py-premiere: subclip");
            });
            how = "attempt" + a;
        } catch (e) {
            errors.push(String(e).slice(0, 80));
        }
    }
    var names = [];
    var after = await (ppro.FolderItem.cast(root)).getItems();
    for (var n = 0; n < after.length; n += 1) {
        names.push(after[n].name);
    }
    var saved = null;
    if (how) {
        saved = await project.saveAs(job.saveAs);
    }
    return { how: how, errors: errors, items: names, saved: saved };
};
