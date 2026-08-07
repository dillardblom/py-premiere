/*
Transport smoke test: report UXP/host versions and the active project.
Proves plugin load, premierepro DOM access, and fullAccess file writes.
*/
module.exports.run = async function (job) {
    var uxp = require("uxp");
    var out = {
        uxpVersion: uxp.versions ? uxp.versions.uxp : null,
        pluginVersion: uxp.versions ? uxp.versions.plugin : null,
    };
    try {
        out.hostName = uxp.host ? uxp.host.name : null;
        out.hostVersion = uxp.host ? uxp.host.version : null;
    } catch (error) {
        out.hostError = String(error);
    }
    try {
        var ppro = require("premierepro");
        out.premiereproKeys = Object.keys(ppro).sort();
        var project = await ppro.Project.getActiveProject();
        if (project) {
            out.projectName = project.name;
            out.projectPath = project.path;
            var sequences = await project.getSequences();
            out.sequenceCount = sequences ? sequences.length : 0;
        } else {
            out.projectName = null;
        }
    } catch (error) {
        out.pproError = (error && error.stack) || String(error);
    }
    return out;
};
