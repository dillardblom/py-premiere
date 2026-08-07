/*
A transition ON A CUT, to pin down what `Alignment` stores when both sides
have footage - Premiere centres a transition dropped on a cut.

Rounds 1-2 established: a head transition stores Alignment 0 and a tail
stores the full duration, `TransitionFactory` can only create VIDEO
transitions (no audio crossfade API exists in UXP or ExtendScript), and
`Constants` has no alignment enum - only `TransitionPosition`, whose values
this run records.

The input project already has two adjacent clips on V1 (built by
py_premiere), so applying to clip 0's end lands on a real cut.
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
    result.api.transitionPosition =
        JSON.stringify(ppro.Constants.TransitionPosition);

    var sequences = await project.getSequences();
    var sequence = sequences[0];
    var clipType = ppro.Constants.TrackItemType
        ? ppro.Constants.TrackItemType.CLIP : 1;
    try {
        var videoTrack = await sequence.getVideoTrack(0);
        project.lockedAccess(function () {
            var items = videoTrack.getTrackItems(clipType, false);
            result.steps.clipCount = items.length;
            var transition = ppro.TransitionFactory.createVideoTransition(
                "ADBE Additive Dissolve");
            var options = ppro.AddTransitionOptions();
            options.setApplyToStart(false);
            var action = items[0].createAddVideoTransitionAction(
                transition, options);
            result.steps.centre = project.executeTransaction(
                function (compound) { compound.addAction(action); },
                "py-premiere: transition on a cut");
        });
        result.steps.saved = await project.saveAs(job.saveAs);
    } catch (e1) {
        result.errors.centre = String(e1);
    }
    return result;
};
