/*
Dump every enum under `ppro.Constants` (and the transition matchName list)
as JSON reference data for value-map decoding. Needs no project.
*/
module.exports.run = async function (job) {
    var ppro = require("premierepro");
    var out = { constants: {} };
    var names = Object.keys(ppro.Constants).sort();
    for (var i = 0; i < names.length; i += 1) {
        var name = names[i];
        var enumObject = ppro.Constants[name];
        var members = {};
        var keys = Object.keys(enumObject);
        for (var j = 0; j < keys.length; j += 1) {
            var value = enumObject[keys[j]];
            var type = typeof value;
            members[keys[j]] = (type === "number" || type === "string"
                || type === "boolean") ? value : String(value);
        }
        out.constants[name] = members;
    }
    try {
        out.videoTransitionMatchNames =
            await ppro.TransitionFactory.getVideoTransitionMatchNames();
    } catch (error) {
        out.videoTransitionMatchNamesError = String(error);
    }
    try {
        out.videoFilterMatchNames =
            await ppro.VideoFilterFactory.getMatchNames();
    } catch (error) {
        out.videoFilterMatchNamesError = String(error);
    }
    try {
        out.audioFilterMatchNames =
            await ppro.AudioFilterFactory.getMatchNames();
    } catch (error) {
        out.audioFilterMatchNamesError = String(error);
    }
    return out;
};
