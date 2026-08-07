/*
py-premiere UXP harness: generic payload runner.

The runner (scripts/run_uxp_in_ppro.ps1) writes `job.json` and `payload.js`
into this folder before `uxp plugin load`. On load this module reads the
job, runs the payload, writes the JSON result to `job.result`, then writes
the marker file at `job.marker` ("DONE" on success, "ERROR: ..." with the
stack on failure). File paths in job.json are absolute with forward
slashes; localFileSystem fullAccess lets the fs module use them directly.

payload.js contract:
    module.exports.run = async function (job) { return jsonSerializable; };
*/
const fs = require("fs");
const os = require("os");

async function bootBeacon(stage) {
    // Written before anything job-dependent so a silent panel (never
    // initialized) is distinguishable from a payload/job failure.
    try {
        const beacon = os.tmpdir().replace(/\\/g, "/")
            + "/pypremiere_uxp_boot.txt";
        await fs.writeFile(beacon, stage + " " + new Date().toISOString(),
            "utf8");
    } catch (ignored) {
        // Beacon is best-effort diagnostics only.
    }
}

function setStatus(text) {
    var element = document.getElementById("status");
    if (element) {
        element.textContent = text;
    }
}

async function main() {
    var job = null;
    await bootBeacon("boot");
    try {
        var jobText = await fs.readFile("plugin:/job.json", "utf8");
        // PowerShell writers may prepend a UTF-8 BOM; JSON.parse rejects it.
        jobText = jobText.replace(new RegExp("^\\uFEFF"), "");
        await bootBeacon("job-read");
        job = JSON.parse(jobText);
        setStatus("running " + (job.name || "payload"));
        var payload = require("./payload.js");
        var result = await payload.run(job);
        if (job.result) {
            await fs.writeFile(
                job.result, JSON.stringify(result, null, 2), "utf8");
        }
        await fs.writeFile(job.marker, "DONE", "utf8");
        setStatus("DONE");
    } catch (error) {
        var detail = "ERROR: " + ((error && error.stack) || String(error));
        setStatus(detail);
        try {
            if (job && job.marker) {
                await fs.writeFile(job.marker, detail, "utf8");
            }
        } catch (ignored) {
            // No marker path available; the runner will time out and the
            // status div still shows the error for interactive debugging.
        }
    }
}

main();
