/*
Footage-interpretation sweep: import the RGBA png (`job.importPath`) into
the open project, introspect the FootageInterpretation API, then set one
field at a time and save `interp_<name>.prproj` into `job.outDir`. Diffing
each file against the base import reveals every field's XML home and enum
mapping.
*/
module.exports.run = async function (job) {
    var ppro = require("premierepro");
    if (!job.outDir || !job.importPath) {
        throw new Error("job.outDir and job.importPath are required");
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
    await project.importFiles([job.importPath]);
    var root = await project.getRootItem();
    var items = await (ppro.FolderItem.cast(root)).getItems();
    var clip = null;
    for (var i = 0; i < items.length; i += 1) {
        if (items[i].name.indexOf("ghost") >= 0) {
            clip = ppro.ClipProjectItem.cast(items[i]);
        }
    }
    if (!clip) {
        throw new Error("no ghost item after import");
    }
    await project.saveAs(job.outDir + "/interp_base.prproj");

    var methods = [];
    var proto = clip;
    while (proto) {
        Object.getOwnPropertyNames(proto).forEach(function (name) {
            if (/interp|footage/i.test(name) && methods.indexOf(name) < 0) {
                methods.push(name);
            }
        });
        proto = Object.getPrototypeOf(proto);
    }

    var interp = await clip.getFootageInterpretation();
    var props = [];
    var p = interp;
    while (p) {
        Object.getOwnPropertyNames(p).forEach(function (name) {
            if (props.indexOf(name) < 0) {
                props.push(name);
            }
        });
        p = Object.getPrototypeOf(p);
    }
    var initial = {};
    props.forEach(function (name) {
        try {
            if (typeof interp[name] !== "function") {
                initial[name] = interp[name];
            }
        } catch (e) {
            initial[name] = "ERR " + String(e);
        }
    });

    async function set(mutate, label) {
        var current = await clip.getFootageInterpretation();
        mutate(current);
        project.lockedAccess(function () {
            var action = clip.createSetFootageInterpretationAction(current);
            project.executeTransaction(function (compound) {
                compound.addAction(action);
            }, "py-premiere: interp " + label);
        });
    }

    async function apply(name, mutate, reset) {
        var error = null;
        try {
            await set(mutate, name);
            await project.saveAs(job.outDir + "/interp_" + name + ".prproj");
            await set(reset, name + "_reset");
        } catch (e) {
            error = String(e);
        }
        return { name: name, error: error };
    }

    // Each field set in ISOLATION from the base, then reset, so every saved
    // file reflects exactly one override.
    var results = [];
    results.push(await apply("field_upper",
        function (x) { x.setFieldType(1); },
        function (x) { x.setFieldType(-1); }));
    results.push(await apply("alpha_straight",
        function (x) { x.setAlphaUsage(1); },
        function (x) { x.setAlphaUsage(3); }));
    results.push(await apply("alpha_premul",
        function (x) { x.setAlphaUsage(2); },
        function (x) { x.setAlphaUsage(3); }));
    results.push(await apply("ignore",
        function (x) { x.setIgnoreAlpha(true); },
        function (x) { x.setIgnoreAlpha(false); }));
    results.push(await apply("invert",
        function (x) { x.setInvertAlpha(true); },
        function (x) { x.setInvertAlpha(false); }));
    return { methods: methods, props: props, initial: initial, results: results };
};
