/*
Retest clip/project-item markers on non-still items (was undefined on a
STILL in 26.3): try `ppro.Markers.getMarkers(<ClipProjectItem>)` on each
root item of 06_api, and if a markers object comes back, add a marker to
the wav item and save to `job.saveAs` - the diff reveals where item markers
are stored (the master clip's own Markers collection is the suspect).
*/
module.exports.run = async function (job) {
    var ppro = require("premierepro");
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
    var root = await project.getRootItem();
    var folder = ppro.FolderItem.cast(root);
    var items = await folder.getItems();
    var report = [];
    var wavMarkers = null;
    for (var i = 0; i < items.length; i += 1) {
        var entry = { name: items[i].name };
        try {
            var clip = ppro.ClipProjectItem.cast(items[i]);
            var markers = await ppro.Markers.getMarkers(clip || items[i]);
            entry.markersObject = markers ? true : false;
            if (markers) {
                var list = await markers.getMarkers();
                entry.count = list.length;
                if (items[i].name.indexOf("tone") >= 0) {
                    wavMarkers = markers;
                }
            }
        } catch (e) {
            entry.error = String(e);
        }
        report.push(entry);
    }

    var added = null;
    if (wavMarkers && job.saveAs) {
        try {
            project.lockedAccess(function () {
                project.executeTransaction(function (compound) {
                    var action = wavMarkers.createAddMarkerAction(
                        "item marker",
                        "Comment",
                        ppro.TickTime.createWithSeconds(0.25),
                        ppro.TickTime.createWithSeconds(0.5),
                        "from py-premiere probe"
                    );
                    compound.addAction(action);
                }, "py-premiere: add item marker");
            });
            var after = await wavMarkers.getMarkers();
            added = { count: after.length };
            await project.saveAs(job.saveAs);
            added.saved = true;
        } catch (e2) {
            added = { error: String(e2) };
        }
    }
    return { report: report, added: added };
};
