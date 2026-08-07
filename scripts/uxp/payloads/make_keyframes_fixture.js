/*
Generate the keyframe-interpolation fixture: make the Opacity param of the
first V1 clip time-varying, add keyframes with KNOWN values and set a
distinct temporal interpolation on each (LINEAR=0, HOLD=4, BEZIER=5 per
Constants.InterpolationMode), then save to `job.saveAs`. The stored
keyframe strings can then be decoded field-by-field against these knowns.
*/
var KEYS = [
    { seconds: 0.5, value: 25, mode: 0 },
    { seconds: 1.5, value: 75, mode: 4 },
    { seconds: 2.5, value: 50, mode: 5 },
    { seconds: 3.5, value: 90, mode: 5 },
];

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
    var clipType = ppro.Constants && ppro.Constants.TrackItemType
        ? ppro.Constants.TrackItemType.CLIP : 1;
    var items = await track.getTrackItems(clipType, false);
    if (!items.length) {
        throw new Error("V1 has no clips");
    }
    var chain = await items[0].getComponentChain();
    var count = await chain.getComponentCount();
    var opacityParam = null;
    for (var i = 0; i < count && !opacityParam; i += 1) {
        var component = await chain.getComponentAtIndex(i);
        var matchName = await component.getMatchName();
        if (matchName === "AE.ADBE Opacity") {
            opacityParam = await component.getParam(0);
        }
    }
    if (!opacityParam) {
        throw new Error("no AE.ADBE Opacity component on the first clip");
    }
    var executed = [];
    project.lockedAccess(function () {
        executed.push(project.executeTransaction(function (compound) {
            compound.addAction(
                opacityParam.createSetTimeVaryingAction(true));
            for (var j = 0; j < KEYS.length; j += 1) {
                var keyframe = opacityParam.createKeyframe(KEYS[j].value);
                keyframe.position =
                    ppro.TickTime.createWithSeconds(KEYS[j].seconds);
                compound.addAction(
                    opacityParam.createAddKeyframeAction(keyframe));
            }
        }, "py-premiere: add keyframes"));
        executed.push(project.executeTransaction(function (compound) {
            for (var j = 0; j < KEYS.length; j += 1) {
                compound.addAction(
                    opacityParam.createSetInterpolationAtKeyframeAction(
                        ppro.TickTime.createWithSeconds(KEYS[j].seconds),
                        KEYS[j].mode, true));
            }
        }, "py-premiere: set interpolation"));
    });
    var stored = [];
    var times = await opacityParam.getKeyframeListAsTickTimes();
    for (var k = 0; k < times.length; k += 1) {
        stored.push({ seconds: times[k].seconds });
    }
    var saved = await project.saveAs(job.saveAs);
    return {
        requested: KEYS,
        executed: executed,
        storedKeyframes: stored,
        saved: saved,
        savedTo: job.saveAs,
    };
};
