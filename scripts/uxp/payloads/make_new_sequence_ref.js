/*
Reference for new-sequence synthesis: create an empty sequence in the open
project (01_empty), then save to `job.saveAs`. The diff against the source
is exactly the object graph a fresh sequence adds - the template
`Project.add_sequence` clones. Introspects the Project for the creation API.
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

    var methods = [];
    var proto = project;
    while (proto) {
        Object.getOwnPropertyNames(proto).forEach(function (name) {
            if (/sequence/i.test(name) && methods.indexOf(name) < 0) {
                methods.push(name);
            }
        });
        proto = Object.getPrototypeOf(proto);
    }

    var error = null;
    var created = null;
    try {
        if (job.presetPath) {
            created = await project.createSequenceWithPresetPath(
                "Seq01", job.presetPath
            );
        } else {
            created = await project.createSequence("Seq01");
        }
    } catch (e) {
        error = String(e);
    }
    var saved = null;
    if (!error) {
        saved = await project.saveAs(job.saveAs);
    }
    return {
        methods: methods,
        created: created ? String(created.name) : null,
        error: error,
        saved: saved,
    };
};
