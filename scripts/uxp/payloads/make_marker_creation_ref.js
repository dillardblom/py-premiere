/*
Reference for marker creation: add one comment marker to the FIRST sequence
that currently has no markers, then save to `job.saveAs`. Diffing against
the source reveals the full wiring Premiere synthesizes for a marker created
from scratch (Marker object + DVAMarker blob + MarkerOwner/Markers pair).
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
    // job.wantMarkers: pick a sequence that ALREADY has markers (append
    // case) vs the default marker-free sequence (collection-creation case).
    var sequences = await project.getSequences();
    var target = null;
    for (var i = 0; i < sequences.length; i += 1) {
        var markersObject = await ppro.Markers.getMarkers(sequences[i]);
        var existing = await markersObject.getMarkers();
        var hasMarkers = existing.length > 0;
        if (hasMarkers === !!job.wantMarkers) {
            target = { sequence: sequences[i], markers: markersObject };
            break;
        }
    }
    if (!target) {
        throw new Error("no matching sequence");
    }
    var executed = null;
    project.lockedAccess(function () {
        var action = target.markers.createAddMarkerAction(
            "created", "Comment",
            ppro.TickTime.createWithSeconds(1.0),
            ppro.TickTime.createWithSeconds(0.5), "made by py-premiere ref");
        executed = project.executeTransaction(function (compound) {
            compound.addAction(action);
        }, "py-premiere: add marker");
    });
    var verify = [];
    var after = await target.markers.getMarkers();
    for (var j = 0; j < after.length; j += 1) {
        verify.push({
            name: await after[j].getName(),
            comments: await after[j].getComments(),
        });
    }
    var saved = await project.saveAs(job.saveAs);
    return {
        sequence: target.sequence.name, executed: executed,
        verify: verify, saved: saved,
    };
};
