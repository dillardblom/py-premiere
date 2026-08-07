/*
Read back the footage interpretation of every clip item in the open
project - so a py-written interpretation can be checked from Premiere's side.
*/
module.exports.run = async function (job) {
    var ppro = require("premierepro");
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
    var out = [];
    for (var i = 0; i < items.length; i += 1) {
        var clip = ppro.ClipProjectItem.cast(items[i]);
        var entry = { name: items[i].name };
        if (clip) {
            try {
                var interp = await clip.getFootageInterpretation();
                entry.alphaUsage = await interp.getAlphaUsage();
                entry.ignoreAlpha = await interp.getIgnoreAlpha();
                entry.invertAlpha = await interp.getInvertAlpha();
                entry.fieldType = await interp.getFieldType();
            } catch (e) {
                entry.error = String(e);
            }
        }
        out.push(entry);
    }
    return { items: out };
};
