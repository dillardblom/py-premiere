/*
Mute V1 of the first sequence, then save to `job.saveAs`. Introspects the
UXP Track object for a mute API (createSetMuteAction, else setMute) so one
run both probes UXP support and produces the muted-track fixture. Diffing
against the source reveals the IsMuted flag's XML home on ClipTrack/Track.
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

    var muteMethods = [];
    var proto = track;
    while (proto) {
        Object.getOwnPropertyNames(proto).forEach(function (name) {
            if (/mute/i.test(name) && muteMethods.indexOf(name) < 0) {
                muteMethods.push(name);
            }
        });
        proto = Object.getPrototypeOf(proto);
    }

    var how = null;
    var err = null;
    try {
        project.lockedAccess(function () {
            var action = track.createSetMuteAction(true);
            project.executeTransaction(function (compound) {
                compound.addAction(action);
            }, "py-premiere: mute track");
        });
        how = "createSetMuteAction";
    } catch (e1) {
        err = String(e1);
        try {
            project.lockedAccess(function () {
                track.setMute(true);
            });
            how = "setMute";
        } catch (e2) {
            err = err + " | " + String(e2);
        }
    }

    var muted = null;
    try {
        muted = await track.isMuted();
    } catch (e) {
        muted = "isMuted() failed: " + String(e);
    }

    var saved = null;
    if (how) {
        saved = await project.saveAs(job.saveAs);
    }
    return {
        muteMethods: muteMethods,
        how: how,
        muted: muted,
        err: err,
        saved: saved,
    };
};
