/*
Transition variants, to pin down `Alignment` semantics and reach audio
transitions.

Round 1 established: `AddTransitionOptions` offers setApplyToStart,
setDuration, setForceSingleSided and setTransitionAlignment, a tail
transition stores Alignment = the full duration (a head stores 0), and
`TransitionFactory.createAudioTransition` does not exist.

This round introspects for the real audio creator and the alignment enum,
then writes a CENTRED transition and an audio crossfade, saving after each
so a pr-compare chain isolates one change at a time.
*/
module.exports.run = async function (job) {
    var ppro = require("premierepro");
    var project = null;
    for (var attempt = 0; attempt < 45 && !project; attempt += 1) {
        project = await ppro.Project.getActiveProject();
        if (!project) {
            await new Promise(function (resolve) { setTimeout(resolve, 2000); });
        }
    }
    if (!project) {
        throw new Error("no active project after 90s");
    }
    var result = { steps: {}, errors: {}, api: {} };

    function members(obj, pattern) {
        var found = [];
        var cursor = obj;
        while (cursor) {
            Object.getOwnPropertyNames(cursor).forEach(function (name) {
                if (pattern.test(name) && found.indexOf(name) < 0) {
                    found.push(name);
                }
            });
            cursor = Object.getPrototypeOf(cursor);
        }
        return found.sort();
    }

    result.api.pproTransition = members(ppro, /transition/i);
    result.api.factory = members(ppro.TransitionFactory, /./);
    result.api.constants = members(ppro.Constants || {}, /align|transition/i);
    var alignEnum = null;
    (result.api.constants || []).forEach(function (name) {
        if (/align/i.test(name)) {
            alignEnum = ppro.Constants[name];
            result.api.alignValues = JSON.stringify(alignEnum);
        }
    });

    var sequences = await project.getSequences();
    var sequence = sequences[0];
    var clipType = ppro.Constants && ppro.Constants.TrackItemType
        ? ppro.Constants.TrackItemType.CLIP : 1;

    // --- centred: a tail transition straddling the cut --------------------
    // A still has media beyond its out point, so both halves have footage.
    try {
        var videoTrack = await sequence.getVideoTrack(0);
        project.lockedAccess(function () {
            var items = videoTrack.getTrackItems(clipType, false);
            var transition = ppro.TransitionFactory.createVideoTransition(
                "ADBE Additive Dissolve");
            var options = ppro.AddTransitionOptions();
            options.setApplyToStart(false);
            var centre = alignEnum
                ? (alignEnum.CENTER !== undefined ? alignEnum.CENTER
                    : (alignEnum.CENTERED !== undefined ? alignEnum.CENTERED
                        : alignEnum.CENTER_ALIGN))
                : undefined;
            result.steps.centreValue = String(centre);
            if (centre !== undefined) {
                options.setTransitionAlignment(centre);
            }
            var action = items[0].createAddVideoTransitionAction(
                transition, options);
            result.steps.centre = project.executeTransaction(
                function (compound) { compound.addAction(action); },
                "py-premiere: centred transition");
        });
        result.steps.centreSaved = await project.saveAs(job.centreSaveAs);
    } catch (e1) {
        result.errors.centre = String(e1);
    }

    // --- audio crossfade on A1 -------------------------------------------
    try {
        var audioTrack = await sequence.getAudioTrack(0);
        var maker = null;
        ["createAudioTransition", "createTransition"].forEach(function (name) {
            if (!maker && typeof ppro.TransitionFactory[name] === "function") {
                maker = name;
            }
        });
        result.steps.audioMaker = String(maker);
        project.lockedAccess(function () {
            var items = audioTrack.getTrackItems(clipType, false);
            if (!items.length) {
                throw new Error("A1 has no clips");
            }
            var crossfade = ppro.TransitionFactory[maker](
                "ADBE Constant Power");
            var options = ppro.AddTransitionOptions();
            options.setApplyToStart(true);
            var action = items[0].createAddAudioTransitionAction(
                crossfade, options);
            result.steps.crossfade = project.executeTransaction(
                function (compound) { compound.addAction(action); },
                "py-premiere: audio crossfade");
        });
        result.steps.crossfadeSaved = await project.saveAs(job.crossfadeSaveAs);
    } catch (e2) {
        result.errors.crossfade = String(e2);
    }
    return result;
};
