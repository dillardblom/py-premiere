/*
Reference for materializing keyframes on an already-stored static scalar:
make the first audio clip's Level time-varying and add two keyframes, then
save to `job.saveAs`. Diffing against the source reveals how Premiere flips
a static param into a keyframed one (IsTimeVarying + the Keyframes element).
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
    var track = await sequences[0].getAudioTrack(0);
    var clipType = ppro.Constants && ppro.Constants.TrackItemType
        ? ppro.Constants.TrackItemType.CLIP : 1;
    var items = await track.getTrackItems(clipType, false);
    var chain = await items[0].getComponentChain();
    var count = await chain.getComponentCount();
    var target = null;
    for (var i = 0; i < count && !target; i += 1) {
        var component = await chain.getComponentAtIndex(i);
        var params = await component.getParamCount();
        for (var p = 0; p < params; p += 1) {
            var param = await component.getParam(p);
            if (param.displayName === "Level") {
                target = param;
                break;
            }
        }
    }
    if (!target) {
        throw new Error("no Level param");
    }
    var executed = null;
    project.lockedAccess(function () {
        executed = project.executeTransaction(function (compound) {
            compound.addAction(target.createSetTimeVaryingAction(true));
            var k1 = target.createKeyframe(0.25);
            k1.position = ppro.TickTime.createWithSeconds(0.25);
            compound.addAction(target.createAddKeyframeAction(k1));
            var k2 = target.createKeyframe(0.75);
            k2.position = ppro.TickTime.createWithSeconds(0.75);
            compound.addAction(target.createAddKeyframeAction(k2));
        }, "py-premiere: materialize keyframes");
    });
    var times = await target.getKeyframeListAsTickTimes();
    var saved = await project.saveAs(job.saveAs);
    return {
        executed: executed,
        keyframeCount: times ? times.length : 0,
        saved: saved,
    };
};
