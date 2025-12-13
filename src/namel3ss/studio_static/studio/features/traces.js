(function (N) {
  N.features = N.features || {};
  const traces = (N.features.traces = N.features.traces || {});
  let ctx = null;

  function getApi() {
    return (ctx && ctx.api) || N.api;
  }

  async function loadTraces() {
    if (typeof window.setStatus === "function") window.setStatus("Loading last trace…");
    try {
      const data = await getApi().jsonRequest("/api/last-trace");
      if (typeof window.renderJsonIn === "function") window.renderJsonIn("traces-content", data);
      if (typeof window.setStatus === "function") window.setStatus("Trace loaded.");
    } catch (err) {
      if (err.message.includes("404")) {
        if (typeof window.renderJsonIn === "function") window.renderJsonIn("traces-content", "No traces available yet.");
        if (typeof window.setStatus === "function") window.setStatus("No traces available yet.");
      } else {
        console.error(err);
        if (typeof window.renderJsonIn === "function") window.renderJsonIn("traces-content", `Error: ${err.message}`);
        if (typeof window.setStatus === "function") window.setStatus("Error loading traces.", true);
      }
    }
  }

  traces.init = function initTraces(context) {
    ctx = context || ctx;
    return undefined;
  };

  traces.loadTraces = loadTraces;
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
