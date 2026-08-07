/*
Set a distinct color label on each top-level project item, then save to
`job.saveAs`. Diffing against the source reveals where the per-item color
label index is stored. Labels: FOREST(5), ROSE(6), MANGO(7), PURPLE(8).
*/
var LABELS = [5, 6, 7, 8];

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
    var items = await root.getItems();
    var applied = [];
    var executed = [];
    var errors = [];
    for (var i = 0; i < items.length; i += 1) {
        var label = LABELS[i % LABELS.length];
        var item = items[i];
        try {
            project.lockedAccess(function () {
                var action = item.createSetColorLabelAction(label);
                executed.push(project.executeTransaction(function (compound) {
                    compound.addAction(action);
                }, "py-premiere: set color label"));
            });
            applied.push({ name: item.name, label: label });
        } catch (error) {
            errors.push({ name: item.name, error: String(error) });
        }
    }
    var verify = [];
    for (var j = 0; j < items.length; j += 1) {
        try {
            verify.push({
                name: items[j].name,
                index: await items[j].getColorLabelIndex(),
            });
        } catch (error) {
            verify.push({ name: items[j].name, error: String(error) });
        }
    }
    var saved = await project.saveAs(job.saveAs);
    return {
        applied: applied, executed: executed, errors: errors,
        verify: verify, saved: saved,
    };
};
