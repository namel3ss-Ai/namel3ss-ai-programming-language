(function (N) {
  N.features = N.features || {};
  const diagnostics = (N.features.diagnostics = N.features.diagnostics || {});
  let ctx = null;

  function getApi() {
    return (ctx && ctx.api) || N.api;
  }

  async function runDiagnostics() {
    const pathsRaw = document.getElementById("diagnostics-paths").value.trim();
    const strict = document.getElementById("diagnostics-strict").checked;
    const summaryOnly = document.getElementById("diagnostics-summary").checked;
    const paths = pathsRaw
      ? pathsRaw
          .split(/\r?\n/)
          .map((p) => p.trim())
          .filter(Boolean)
      : [];
    if (typeof window.setStatus === "function") window.setStatus("Running diagnostics…");
    try {
      const body = { paths, strict, summary_only: summaryOnly };
      const data = await getApi().jsonRequest("/api/diagnostics", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (typeof window.renderJsonIn === "function") window.renderJsonIn("diagnostics-content", data);
      if (typeof window.setStatus === "function") window.setStatus("Diagnostics complete.");
    } catch (err) {
      console.error(err);
      if (typeof window.renderJsonIn === "function") window.renderJsonIn("diagnostics-content", `Error: ${err.message}`);
      if (typeof window.setStatus === "function") window.setStatus("Error running diagnostics.", true);
    }
  }

  diagnostics.init = function initDiagnostics(context) {
    ctx = context || ctx;
    return undefined;
  };

  diagnostics.runDiagnostics = runDiagnostics;
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
