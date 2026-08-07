/*
Generate a transition fixture - the first corpus content ExtendScript
cannot create (no transition DOM API; QE addTransition is gone in 26.x).

Adds a video transition to the start of the first clip on V1 of the active
sequence, then saves to `job.saveAs`. Set `job.transition` to override the
default (first "dissolve" matchName).

The DOM handles (track item, transition, action) are only valid inside a
`project.lockedAccess` block and the action must be created and executed in
the same block - using them across an await raises "The script object is no
longer valid" (pattern from AdobeDocs uxp-premiere-pro-samples transition.ts).
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
    var names = await ppro.TransitionFactory.getVideoTransitionMatchNames();
    var matchName = job.transition;
    if (!matchName || names.indexOf(matchName) < 0) {
        var dissolves = names.filter(function (name) {
            return /dissolve/i.test(name);
        });
        matchName = dissolves.length ? dissolves[0] : names[0];
    }
    var sequences = await project.getSequences();
    if (!sequences.length) {
        throw new Error("project has no sequence");
    }
    var sequence = sequences[0];
    var track = await sequence.getVideoTrack(0);
    var clipType = ppro.Constants && ppro.Constants.TrackItemType
        ? ppro.Constants.TrackItemType.CLIP : 1;

    var result = { used: matchName, availableMatchNames: names };
    project.lockedAccess(function () {
        var items = track.getTrackItems(clipType, false);
        if (!items.length) {
            throw new Error("V1 has no clips");
        }
        var transition = ppro.TransitionFactory.createVideoTransition(
            matchName);
        var options = ppro.AddTransitionOptions();
        options.setApplyToStart(true);
        var action = items[0].createAddVideoTransitionAction(
            transition, options);
        result.executed = project.executeTransaction(function (compound) {
            compound.addAction(action);
        }, "py-premiere: add transition");
    });
    result.saved = await project.saveAs(job.saveAs);
    result.savedTo = job.saveAs;
    return result;
};
