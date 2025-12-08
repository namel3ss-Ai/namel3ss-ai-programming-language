(() => {
  const loadedPanels = new Set();

  function getApiKey() {
    const el = document.getElementById("api-key-input");
    return el ? el.value.trim() : "";
  }

  function setStatus(message, isError = false) {
    const el = document.getElementById("studio-status");
    if (!el) return;
    el.textContent = message;
    el.classList.toggle("status-error", Boolean(isError));
  }

  async function jsonRequest(url, options = {}) {
    const headers = options.headers ? { ...options.headers } : {};
    if (options.body) {
      headers["Content-Type"] = "application/json";
    }
    const apiKey = getApiKey();
    if (apiKey) {
      headers["X-API-Key"] = apiKey;
    }
    const resp = await fetch(url, { ...options, headers });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`${resp.status} ${resp.statusText}: ${text || "No response body"}`);
    }
    const contentType = resp.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return resp.json();
    }
    return resp.text();
  }

  function renderJsonIn(elementId, data) {
    const el = document.getElementById(elementId);
    if (!el) return;
    if (data === undefined || data === null) {
      el.textContent = "No data.";
      return;
    }
    const formatted = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    el.textContent = formatted;
  }

  async function loadProviderStatus() {
    const pill = document.getElementById("provider-status");
    if (!pill) return;
    pill.textContent = "Provider: checking…";
    pill.classList.remove("warn", "error");
    try {
      const status = await jsonRequest("/api/providers/status");
      const defaultName = status.default || "none";
      const primary = (status.providers || []).find((p) => p.name === defaultName) || (status.providers || [])[0];
      if (!primary) {
        pill.textContent = "Provider: not configured";
        pill.classList.add("warn");
        return;
      }
      const icon = primary.last_check_status === "ok" ? "✅" : primary.last_check_status === "unauthorized" ? "❌" : "⚠️";
      if (primary.last_check_status === "missing_key") {
        pill.classList.add("warn");
      } else if (primary.last_check_status === "unauthorized") {
        pill.classList.add("error");
      }
      const label = primary.last_check_status === "ok" ? "OK" : primary.last_check_status.replace("_", " ");
      pill.textContent = `${icon} Provider: ${primary.name} (${primary.type}) — ${label}`;
    } catch (err) {
      pill.textContent = `Provider: error ${err.message}`;
      pill.classList.add("error");
    }
  }

  function activatePanel(panel) {
    document.querySelectorAll(".studio-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.panel === panel);
    });
    document.querySelectorAll("section.panel").forEach((sec) => {
      sec.classList.toggle("active", sec.id === `panel-${panel}`);
    });
    if (!loadedPanels.has(panel)) {
      loadedPanels.add(panel);
      switch (panel) {
        case "overview":
          loadOverview();
          break;
        case "traces":
          loadTraces();
          break;
        case "memory":
          loadMemory();
          break;
        case "rag":
          runRagQuery();
          break;
        case "diagnostics":
          runDiagnostics();
          break;
        default:
          break;
      }
    }
  }

  async function loadOverview() {
    setStatus("Loading overview…");
    try {
      const data = await jsonRequest("/api/studio-summary");
      renderJsonIn("overview-content", data);
      setStatus("Overview loaded.");
    } catch (err) {
      console.error(err);
      renderJsonIn("overview-content", `Error loading overview: ${err.message}`);
      setStatus("Error loading overview.", true);
    }
  }

  async function runApp() {
    const source = document.getElementById("run-app-source").value;
    const appName = document.getElementById("run-app-name").value.trim();
    const payloadRaw = document.getElementById("run-app-payload").value.trim();
    let extraPayload = {};
    if (!appName) {
      renderJsonIn("run-app-output", "App name is required.");
      setStatus("App name is required.", true);
      return;
    }
    if (payloadRaw) {
      try {
        extraPayload = JSON.parse(payloadRaw);
      } catch (err) {
        renderJsonIn("run-app-output", `Invalid JSON payload: ${err.message}`);
        setStatus("Invalid JSON payload.", true);
        return;
      }
    }
    setStatus("Running app…");
    try {
      const body = { source, app_name: appName, ...extraPayload };
      const data = await jsonRequest("/api/run-app", {
        method: "POST",
        body: JSON.stringify(body),
      });
      renderJsonIn("run-app-output", data);
      setStatus("App run complete.");
    } catch (err) {
      console.error(err);
      renderJsonIn("run-app-output", `Error: ${err.message}`);
      setStatus("Error running app.", true);
    }
  }

  async function runFlow() {
    const source = document.getElementById("run-flow-source").value;
    const flowName = document.getElementById("run-flow-name").value.trim();
    const stateRaw = document.getElementById("run-flow-state").value.trim();
    let statePayload = {};
    if (!flowName) {
      renderJsonIn("run-flow-output", "Flow name is required.");
      setStatus("Flow name is required.", true);
      return;
    }
    if (stateRaw) {
      try {
        statePayload = JSON.parse(stateRaw);
      } catch (err) {
        renderJsonIn("run-flow-output", `Invalid JSON state: ${err.message}`);
        setStatus("Invalid JSON state.", true);
        return;
      }
    }
    setStatus("Running flow…");
    try {
      const body = { source, flow: flowName, ...statePayload };
      const data = await jsonRequest("/api/run-flow", {
        method: "POST",
        body: JSON.stringify(body),
      });
      renderJsonIn("run-flow-output", data);
      setStatus("Flow run complete.");
    } catch (err) {
      console.error(err);
      renderJsonIn("run-flow-output", `Error: ${err.message}`);
      setStatus("Error running flow.", true);
    }
  }

  async function loadTraces() {
    setStatus("Loading last trace…");
    try {
      const data = await jsonRequest("/api/last-trace");
      renderJsonIn("traces-content", data);
      setStatus("Trace loaded.");
    } catch (err) {
      if (err.message.includes("404")) {
        renderJsonIn("traces-content", "No traces available yet.");
        setStatus("No traces available yet.");
      } else {
        console.error(err);
        renderJsonIn("traces-content", `Error: ${err.message}`);
        setStatus("Error loading traces.", true);
      }
    }
  }

  function loadMemory() {
    renderJsonIn(
      "memory-content",
      "Memory endpoints are not configured in this server build."
    );
    setStatus("Memory panel ready.");
  }

  async function runRagQuery() {
    const query = document.getElementById("rag-query").value.trim();
    const indexesRaw = document.getElementById("rag-indexes").value.trim();
    const source = document.getElementById("rag-source").value;
    const indexes = indexesRaw ? indexesRaw.split(",").map((i) => i.trim()).filter(Boolean) : null;
    if (!query) {
      renderJsonIn("rag-content", "Query is required.");
      setStatus("Query is required.", true);
      return;
    }
    setStatus("Running RAG query…");
    try {
      const body = { query, code: source };
      if (indexes && indexes.length) {
        body.indexes = indexes;
      }
      const data = await jsonRequest("/api/rag/query", {
        method: "POST",
        body: JSON.stringify(body),
      });
      renderJsonIn("rag-content", data);
      setStatus("RAG query complete.");
    } catch (err) {
      console.error(err);
      renderJsonIn("rag-content", `Error: ${err.message}`);
      setStatus("Error running RAG query.", true);
    }
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
    setStatus("Running diagnostics…");
    try {
      const body = { paths, strict, summary_only: summaryOnly };
      const data = await jsonRequest("/api/diagnostics", {
        method: "POST",
        body: JSON.stringify(body),
      });
      renderJsonIn("diagnostics-content", data);
      setStatus("Diagnostics complete.");
    } catch (err) {
      console.error(err);
      renderJsonIn("diagnostics-content", `Error: ${err.message}`);
      setStatus("Error running diagnostics.", true);
    }
  }

  function initTabs() {
    document.querySelectorAll(".studio-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        activatePanel(tab.dataset.panel);
      });
    });
  }

  function initButtons() {
    const actions = {
      "overview-reload": loadOverview,
      "traces-reload": loadTraces,
      "memory-reload": loadMemory,
      "rag-run": runRagQuery,
      "diagnostics-run": runDiagnostics,
      "run-app": runApp,
      "run-flow": runFlow,
    };
    document.querySelectorAll("button.reload").forEach((btn) => {
      const action = btn.dataset.action;
      if (actions[action]) {
        btn.addEventListener("click", actions[action]);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initButtons();
    activatePanel("overview");
    loadProviderStatus();
    setStatus("Ready.");
  });
})();
