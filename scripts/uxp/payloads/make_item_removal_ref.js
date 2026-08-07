/*
Reference for project-item removal: delete the first clip item under the
root (03_one_clip's bmp), then save to `job.saveAs`. Diffing against the
source reveals the exact object graph Premiere deletes with a panel item
(MasterClip, template clips, Source, Media, streams...). Introspects the
root FolderItem for the removal API first.
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
    var folder = ppro.FolderItem.cast(root);
    var items = await folder.getItems();
    if (!items.length) {
        throw new Error("root has no items");
    }

    var methods = [];
    var proto = folder;
    while (proto) {
        Object.getOwnPropertyNames(proto).forEach(function (name) {
            if (/remove|delete/i.test(name) && methods.indexOf(name) < 0) {
                methods.push(name);
            }
        });
        proto = Object.getPrototypeOf(proto);
    }

    var how = null;
    var errors = [];
    var candidates = ["createRemoveItemAction", "createDeleteItemAction"];
    for (var i = 0; i < candidates.length && !how; i += 1) {
        var method = candidates[i];
        if (typeof folder[method] !== "function") {
            continue;
        }
        try {
            project.lockedAccess(function () {
                project.executeTransaction(function (compound) {
                    compound.addAction(folder[method](items[0]));
                }, "py-premiere: remove item");
            });
            how = method;
        } catch (e) {
            errors.push(method + ": " + String(e));
        }
    }

    var remaining = (await folder.getItems()).length;
    var saved = null;
    if (how) {
        saved = await project.saveAs(job.saveAs);
    }
    return {
        methods: methods,
        how: how,
        errors: errors,
        remaining: remaining,
        saved: saved,
    };
};
