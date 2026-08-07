// Open a project silently for the UXP harness, then idle (do NOT quit).
//
// The UXP runner launches Premiere with
//   /C es.processFile <this>   and PYPREMIERE_OPEN=<project path>
// openDocument(path, suppressConversion, suppressLocateMedia, suppressWarnings)
// suppresses the conversion / locate-media / "path does not exist" dialogs
// that a bare command-line open raises. Writes PYPREMIERE_OPEN_MARKER with
// the opened project name so the runner knows the project is live before it
// loads the plugin.
(function () {
    var projectPath = $.getenv("PYPREMIERE_OPEN");
    var markerPath = $.getenv("PYPREMIERE_OPEN_MARKER");
    var status = "ERROR: no project path";
    try {
        if (projectPath) {
            app.openDocument(projectPath, true, true, true);
            status = "OPENED: " + app.project.name;
        }
    } catch (error) {
        status = "ERROR: " + error.toString();
    }
    if (markerPath) {
        var file = new File(markerPath);
        file.open("w");
        file.writeln(status);
        file.close();
    }
})();
