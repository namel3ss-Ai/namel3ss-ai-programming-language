(function (N) {
  N.features = N.features || {};
  const status = (N.features.status = N.features.status || {});

  status.renderBanner = function renderBanner(message, tone = "warn") {
    const banner = document.getElementById("status-banner");
    if (!banner) return;
    if (!message) {
      banner.textContent = "";
      banner.classList.remove("visible", "warn", "error");
      return;
    }
    banner.textContent = message;
    banner.classList.add("visible");
    banner.classList.toggle("warn", tone === "warn");
    banner.classList.toggle("error", tone === "error");
  };

  status.loadProviderStatus = async function loadProviderStatus() {
    const pill = document.getElementById("provider-status");
    if (!pill) return;
    pill.textContent = "Provider: checking…";
    pill.classList.remove("warn", "error");
    try {
      const jsonRequest = window.jsonRequest || N.api?.jsonRequest;
      const statusResp = await jsonRequest("/api/providers/status");
      const defaultName = statusResp.default || "none";
      const primary =
        (statusResp.providers || []).find((p) => p.name === defaultName) || (statusResp.providers || [])[0];
      if (!primary) {
        pill.textContent = "Provider: not configured";
        pill.classList.add("warn");
        return;
      }
      const icon =
        primary.last_check_status === "ok"
          ? "✅"
          : primary.last_check_status === "unauthorized"
          ? "❌"
          : "⚠️";
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
  };

  status.loadStudioStatus = async function loadStudioStatus() {
    try {
      const jsonRequest = window.jsonRequest || N.api?.jsonRequest;
      const statusResp = await jsonRequest("/api/studio/status");
      if (statusResp.ir_status === "error") {
        const err = statusResp.ir_error || {};
        const loc = [err.file, err.line, err.column].filter(Boolean).join(":");
        const prefix = loc ? `${loc}: ` : "";
        const message = `Your project has errors. ${prefix}${err.message || ""}`.trim();
        status.renderBanner(`${message} `, "error");
        const banner = document.getElementById("status-banner");
        if (banner) {
          const btn = document.createElement("button");
          btn.className = "reload";
          btn.textContent = "Ask Studio about this error";
          btn.addEventListener("click", () => {
            if (typeof window.prefillAsk === "function") {
              window.prefillAsk(`${message} How do I fix this?`, { kind: "error", error: err }, true);
            }
          });
          banner.appendChild(document.createTextNode(" "));
          banner.appendChild(btn);
        }
        if (typeof window.setStatus === "function") window.setStatus("Your project has errors.", true);
        return;
      }
      const aiFiles = statusResp.ai_files || 0;
      const aiPaths = statusResp.ai_file_paths || [];
      if (aiFiles === 0) {
        status.renderBanner("No .ai files found. Add one to get started.", "warn");
      } else if (aiFiles === 1 && aiPaths.length === 1 && ["starter.ai", "app.ai", "main.ai"].includes(aiPaths[0])) {
        status.renderBanner("Starter project created. Edit starter.ai to begin.", "warn");
      } else if (statusResp.watcher_supported === false) {
        status.renderBanner("File system watcher unavailable; changes will not auto-reload.", "warn");
      } else if (statusResp.watcher_active === false) {
        status.renderBanner("File system watcher inactive; changes will not auto-reload.", "warn");
      } else if (statusResp.studio_static_available === false) {
        status.renderBanner("Packaged Studio assets not found. Reinstall or rebuild (development only).", "warn");
      } else {
        status.renderBanner("");
      }
    } catch (err) {
      status.renderBanner(`Could not check project status: ${err.message}`, "warn");
      if (typeof window.setStatus === "function") window.setStatus("Status check failed.", true);
    }
  };

  status.reparseNow = async function reparseNow() {
    if (typeof window.setStatus === "function") window.setStatus("Re-parsing…");
    try {
      const jsonRequest = window.jsonRequest || N.api?.jsonRequest;
      const resp = await jsonRequest("/api/studio/reparse", { method: "POST" });
      const errors = resp.errors || [];
      if (resp.success) {
        status.renderBanner(`IR rebuilt at ${resp.timestamp || ""}`, "warn");
        if (typeof window.setStatus === "function") window.setStatus("Re-parse complete.");
      } else if (errors.length) {
        const first = errors[0] || {};
        const msg = `${first.file || "program"}${first.line ? ":" + first.line : ""}: ${first.message || "IR error"}`;
        status.renderBanner(`IR contains errors (${errors.length}). ${msg}`, "error");
        if (typeof window.setStatus === "function") window.setStatus("Re-parse encountered errors.", true);
        if (typeof window.prefillAsk === "function") window.prefillAsk(`Explain this IR error and how to fix it: ${msg}`, { kind: "error", error: first }, false);
      } else {
        status.renderBanner("IR re-parse failed.", "error");
        if (typeof window.setStatus === "function") window.setStatus("Re-parse failed.", true);
      }
      if (typeof window.loadStudioStatus === "function") window.loadStudioStatus();
      if (typeof window.loadCanvas === "function") window.loadCanvas();
      if (typeof window.loadStudioFlows === "function") window.loadStudioFlows();
      if (typeof window.loadRagPipelinesList === "function") window.loadRagPipelinesList();
      if (typeof window.loadWarnings === "function") window.loadWarnings();
      const inspectorPanelActive = document.getElementById("panel-inspector")?.classList.contains("active");
      if (inspectorPanelActive && typeof window.loadInspector === "function") {
        const kind = document.getElementById("inspector-kind")?.value;
        const name = document.getElementById("inspector-entity")?.value;
        if (kind && name) {
          window.loadInspector(kind, name);
        }
      }
    } catch (err) {
      status.renderBanner(`Re-parse failed: ${err.message}`, "error");
      if (typeof window.setStatus === "function") window.setStatus("Re-parse failed.", true);
    }
  };

  status.init = function init(ctx) {
    status._ctx = ctx || status._ctx || null;
    return undefined;
  };
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
