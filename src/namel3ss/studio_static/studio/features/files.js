(function (N) {
  N.features = N.features || {};
  const files = (N.features.files = N.features.files || {});
  let ctx = null;

  function getApi() {
    return (ctx && ctx.api) || N.api;
  }

  async function runApp() {
    const source = document.getElementById("run-app-source").value;
    const appName = document.getElementById("run-app-name").value.trim();
    const payloadRaw = document.getElementById("run-app-payload").value.trim();
    let extraPayload = {};
    if (!appName) {
      if (typeof window.renderJsonIn === "function") window.renderJsonIn("run-app-output", "App name is required.");
      if (typeof window.setStatus === "function") window.setStatus("App name is required.", true);
      return;
    }
    if (payloadRaw) {
      try {
        extraPayload = JSON.parse(payloadRaw);
      } catch (err) {
        if (typeof window.renderJsonIn === "function") window.renderJsonIn("run-app-output", `Invalid JSON payload: ${err.message}`);
        if (typeof window.setStatus === "function") window.setStatus("Invalid JSON payload.", true);
        return;
      }
    }
    if (typeof window.setStatus === "function") window.setStatus("Running app…");
    try {
      const body = { source, app_name: appName, ...extraPayload };
      const data = await getApi().jsonRequest("/api/run-app", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (typeof window.renderJsonIn === "function") window.renderJsonIn("run-app-output", data);
      if (typeof window.setStatus === "function") window.setStatus("App run complete.");
    } catch (err) {
      console.error(err);
      if (typeof window.renderJsonIn === "function") window.renderJsonIn("run-app-output", `Error: ${err.message}`);
      if (typeof window.setStatus === "function") window.setStatus("Error running app.", true);
    }
  }

  async function runFlow() {
    const source = document.getElementById("run-flow-source").value;
    const flowName = document.getElementById("run-flow-name").value.trim();
    const stateRaw = document.getElementById("run-flow-state").value.trim();
    let statePayload = {};
    if (!flowName) {
      if (typeof window.renderJsonIn === "function") window.renderJsonIn("run-flow-output", "Flow name is required.");
      if (typeof window.setStatus === "function") window.setStatus("Flow name is required.", true);
      return;
    }
    if (stateRaw) {
      try {
        statePayload = JSON.parse(stateRaw);
      } catch (err) {
        if (typeof window.renderJsonIn === "function") window.renderJsonIn("run-flow-output", `Invalid JSON state: ${err.message}`);
        if (typeof window.setStatus === "function") window.setStatus("Invalid JSON state.", true);
        return;
      }
    }
    if (typeof window.setStatus === "function") window.setStatus("Running flow…");
    try {
      const body = { source, flow: flowName, ...statePayload };
      const data = await getApi().jsonRequest("/api/run-flow", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (typeof window.renderJsonIn === "function") window.renderJsonIn("run-flow-output", data);
      if (typeof window.setStatus === "function") window.setStatus("Flow run complete.");
    } catch (err) {
      console.error(err);
      if (typeof window.renderJsonIn === "function") window.renderJsonIn("run-flow-output", `Error: ${err.message}`);
      if (typeof window.setStatus === "function") window.setStatus("Error running flow.", true);
    }
  }

  files.init = function initFiles(context) {
    ctx = context || ctx;
    return undefined;
  };

  files.runApp = runApp;
  files.runFlow = runFlow;
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
