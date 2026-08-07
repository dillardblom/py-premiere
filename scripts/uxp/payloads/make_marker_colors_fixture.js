/*
Generate the marker-colors fixture: set a distinct colorIndex on each of
the active project's first-sequence markers, then save to `job.saveAs`.
Diffing against the source project reveals where the color lives in the
DVAMarker blob. Default colors (corpus fixture 08): RED=1, YELLOW=4,
BLUE=6, CYAN=7; override with `job.colors` (used with the remaining
indices to decode the full palette).
*/
var DEFAULT_COLORS = [1, 4, 6, 7];

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
    if (!sequences.length) {
        throw new Error("project has no sequence");
    }
    var markersObject = await ppro.Markers.getMarkers(sequences[0]);
    var markers = await markersObject.getMarkers();
    if (!markers.length) {
        throw new Error("sequence has no markers");
    }
    var colors = job.colors || DEFAULT_COLORS;
    var applied = [];
    var executed = [];
    project.lockedAccess(function () {
        for (var i = 0; i < markers.length; i += 1) {
            var color = colors[i % colors.length];
            var action = markers[i].createSetColorByIndexAction(color);
            executed.push(project.executeTransaction(function (compound) {
                compound.addAction(action);
            }, "py-premiere: set marker color"));
            applied.push(color);
        }
    });
    var verify = [];
    for (var j = 0; j < markers.length; j += 1) {
        verify.push({
            name: await markers[j].getName(),
            colorIndex: await markers[j].getColorIndex(),
        });
    }
    var saved = await project.saveAs(job.saveAs);
    return {
        applied: applied,
        executed: executed,
        verify: verify,
        saved: saved,
        savedTo: job.saveAs,
    };
};
