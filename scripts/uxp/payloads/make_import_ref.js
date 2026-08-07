/*
Reference for `import_files`: import `job.importPath` into the open project
(03_one_clip), then save to `job.saveAs`. Diffing against the source shows
the exact object graph Premiere synthesizes for a fresh still import -
including the opaque Media fields (ModificationState, FileKey,
ContentAndMetadataState). Introspects the Project object for the import API.
*/
module.exports.run = async function (job) {
    var ppro = require("premierepro");
    if (!job.saveAs || !(job.importPath || job.importPaths)) {
        throw new Error("job.saveAs and importPath(s) are required");
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

    var methods = [];
    var proto = project;
    while (proto) {
        Object.getOwnPropertyNames(proto).forEach(function (name) {
            if (/import/i.test(name) && methods.indexOf(name) < 0) {
                methods.push(name);
            }
        });
        proto = Object.getPrototypeOf(proto);
    }

    var how = null;
    var error = null;
    var paths = job.importPaths || [job.importPath];
    try {
        var imported = await project.importFiles(paths);
        how = "importFiles";
        error = imported === false ? "importFiles returned false" : null;
    } catch (e) {
        error = String(e);
    }

    var root = await project.getRootItem();
    var folder = ppro.FolderItem.cast(root);
    var names = [];
    var items = await folder.getItems();
    for (var i = 0; i < items.length; i += 1) {
        names.push(items[i].name);
    }
    var saved = null;
    if (how && !error) {
        saved = await project.saveAs(job.saveAs);
    }
    return { methods: methods, how: how, error: error, items: names, saved: saved };
};
