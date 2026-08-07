/*
Probe ClipProjectItem read attributes + the subclip/offline/adjustment
APIs on 06_api, and dump the values Premiere reports so their XML homes
can be located.
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

    function methods(object, pattern) {
        var out = [];
        var proto = object;
        while (proto) {
            Object.getOwnPropertyNames(proto).forEach(function (name) {
                if (pattern.test(name) && out.indexOf(name) < 0) {
                    out.push(name);
                }
            });
            proto = Object.getPrototypeOf(proto);
        }
        return out;
    }

    var report = { items: [] };
    for (var i = 0; i < items.length; i += 1) {
        var clip = ppro.ClipProjectItem.cast(items[i]);
        var entry = { name: items[i].name };
        if (clip) {
            if (i === 0) {
                report.clipMethods = methods(clip, /Offline|Adjustment|SubClip|Start|InPoint|OutPoint|Sequence|Proxy|Multicam|Merged/i);
            }
            for (var m = 0; m < (report.clipMethods || []).length; m += 1) {
                var name = report.clipMethods[m];
                try {
                    if (name.indexOf("get") === 0 || name.indexOf("is") === 0
                        || name.indexOf("has") === 0) {
                        var value = await clip[name]();
                        if (value && value.ticks !== undefined) {
                            value = { ticks: value.ticks, seconds: value.seconds };
                        }
                        entry[name] = value;
                    }
                } catch (e) {
                    entry[name] = "ERR " + String(e).slice(0, 40);
                }
            }
        }
        report.items.push(entry);
    }
    return report;
};
