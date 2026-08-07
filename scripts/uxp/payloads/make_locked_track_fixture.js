/*
Lock V1 of the first sequence, then save to `job.saveAs`. Introspects the
UXP Track object for a lock API (setLocked/setLock/lock) so one run both
probes UXP support and produces the locked-track fixture - the XML home of
the lock flag is unknown (no IsLocked in any fixture), so diffing against the
source reveals it.
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
    var sequences = await project.getSequences();
    var track = await sequences[0].getVideoTrack(0);

    var lockMethods = [];
    var proto = track;
    while (proto) {
        Object.getOwnPropertyNames(proto).forEach(function (name) {
            if (/lock/i.test(name) && lockMethods.indexOf(name) < 0) {
                lockMethods.push(name);
            }
        });
        proto = Object.getPrototypeOf(proto);
    }

    var candidates = ["setLocked", "setLock", "lock"];
    var how = null;
    var errors = [];
    for (var i = 0; i < candidates.length && !how; i += 1) {
        var method = candidates[i];
        if (typeof track[method] !== "function") {
            continue;
        }
        try {
            project.lockedAccess(function () {
                track[method](true);
            });
            how = method;
        } catch (e) {
            errors.push(method + ": " + String(e));
        }
    }

    var saved = null;
    if (how) {
        saved = await project.saveAs(job.saveAs);
    }
    return {
        lockMethods: lockMethods,
        how: how,
        errors: errors,
        saved: saved,
    };
};
