/*
Generate an audio-param fixture: materialize the intrinsic Volume of the
first audio clip by making its Level param time-varying and adding a
keyframe with a known value, then save to `job.saveAs`. Volume is
runtime-synthesized at default (like video Motion/Opacity), so this forces
it into the stored graph for parser coverage of audio ComponentParams.
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
    if (!items.length) {
        throw new Error("A1 has no clips");
    }
    var chain = await items[0].getComponentChain();
    var count = await chain.getComponentCount();
    var survey = [];
    var target = null;
    for (var i = 0; i < count; i += 1) {
        var component = await chain.getComponentAtIndex(i);
        var matchName = await component.getMatchName();
        var paramCount = await component.getParamCount();
        var params = [];
        for (var p = 0; p < paramCount; p += 1) {
            var param = await component.getParam(p);
            params.push(param.displayName);
            if (!target && /level|volume/i.test(param.displayName)) {
                target = param;
            }
        }
        survey.push({ matchName: matchName, params: params });
    }
    if (!target) {
        throw new Error("no Level/Volume param found: "
            + JSON.stringify(survey));
    }
    var executed = null;
    project.lockedAccess(function () {
        executed = project.executeTransaction(function (compound) {
            // Static non-default level materializes the intrinsic Volume
            // without keyframing it (a distinctive stored value).
            var keyframe = target.createKeyframe(0.35);
            compound.addAction(target.createSetValueAction(keyframe, true));
        }, "py-premiere: set audio volume level");
    });
    var verify = await target.getStartValue();
    var saved = await project.saveAs(job.saveAs);
    return { survey: survey, executed: executed, verify: verify, saved: saved };
};
