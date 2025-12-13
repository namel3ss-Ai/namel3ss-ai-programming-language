(function (N) {
  const panels = (N.panels = N.panels || {});
  const consolePanel = (panels.console = panels.console || {});
  const state = N.state || {};

  consolePanel.renderLogs = function renderLogs(entries) {
    const container = document.getElementById("logs-content");
    if (!container) return;
    if (!entries || !entries.length) {
      container.innerHTML = '<div class="log-entry">No logs yet.</div>';
      return;
    }
    const html = entries
      .map((entry) => {
        const { ts, level, event, detailText } = N.utils.formatLogLine(entry);
        const freshCls = entry.__fresh ? " fresh" : "";
        return `<div class="log-entry${freshCls}">
          <div>${ts}</div>
          <div class="log-level-${level}">${level}</div>
          <div>${event}${detailText ? " — " + detailText : ""}</div>
        </div>`;
      })
      .join("");
    container.innerHTML = html;
    container.scrollTop = container.scrollHeight;
    entries.forEach((entry) => delete entry.__fresh);
  };

  consolePanel.connectLogsStream = function connectLogsStream() {
    const container = document.getElementById("logs-content");
    if (!container) return;
    const entries = [];
    function push(entry) {
      entry.__fresh = true;
      entries.push(entry);
      if (entries.length > 300) entries.shift();
      consolePanel.renderLogs(entries);
    }
    N.api
      .streamLogs()
      .then(async (resp) => {
        if (!resp.ok || !resp.body) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n");
          buffer = parts.pop() || "";
          for (const part of parts) {
            if (!part.trim()) continue;
            try {
              const parsed = JSON.parse(part);
              push(parsed);
            } catch (err) {
              // ignore malformed lines
            }
          }
        }
      })
      .catch(() => {
        container.innerHTML = '<div class="log-entry">Logs stream unavailable.</div>';
      });
  };

  consolePanel.renderWarningsIndicator = function renderWarningsIndicator() {
    const btn = document.getElementById("warnings-toggle");
    const countEl = document.getElementById("warnings-count");
    if (!btn || !countEl) return;
    const count = state.warningsCache.length;
    countEl.textContent = count;
    btn.classList.toggle("has-warnings", count > 0);
  };

  consolePanel.goToWarning = function goToWarning(w) {
    const kind = (w.entity_kind || "").toLowerCase();
    const name = w.entity_name || "";
    if (!kind || !name) return;
    if (kind === "rag") {
      if (window.openRagPipeline) window.openRagPipeline(name, true);
      return;
    }
    const inspectorKinds = ["flow", "page", "ai", "agent", "tool", "memory", "app"];
    if (inspectorKinds.includes(kind)) {
      const kindSelect = document.getElementById("inspector-kind");
      const entitySelect = document.getElementById("inspector-entity");
      if (kindSelect) kindSelect.value = kind;
      if (entitySelect) entitySelect.value = name;
      if (window.activatePanel) window.activatePanel("inspector");
      if (window.loadInspector) window.loadInspector(kind, name);
    }
  };

  consolePanel.renderWarningsPanel = function renderWarningsPanel(errorText) {
    const panel = document.getElementById("warnings-panel");
    if (!panel) return;
    if (errorText) {
      panel.innerHTML = `<div class="warning-card"><div class="warning-main">${N.utils.escapeHtml(errorText)}</div></div>`;
      return;
    }
    if (!state.warningsCache.length) {
      panel.innerHTML = '<div class="warning-card"><div class="warning-main">No warnings detected.</div></div>';
      return;
    }
    panel.innerHTML = `<div class="warning-list">
      ${state.warningsCache
        .map(
          (w, idx) =>
            `<div class="warning-card" data-index="${idx}">
              <div class="warning-main">
                <div class="warning-badge">${N.utils.escapeHtml(w.code || "WARN")}</div>
                <div class="warning-msg">${N.utils.escapeHtml(w.message || "")}</div>
                <div class="warning-meta">${N.utils.escapeHtml(w.entity_kind || "")}: ${N.utils.escapeHtml(w.entity_name || "")}${w.file ? " • " + N.utils.escapeHtml(w.file) : ""}</div>
              </div>
              <div class="warning-actions">
                <button class="reload warning-goto" data-idx="${idx}">View</button>
                <button class="reload warning-ask" data-idx="${idx}">Ask Studio</button>
              </div>
            </div>`
        )
        .join("")}
    </div>`;
    panel.querySelectorAll(".warning-goto").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.dataset.idx || "0");
        const w = state.warningsCache[idx];
        if (w) {
          consolePanel.goToWarning(w);
        }
      });
    });
    panel.querySelectorAll(".warning-ask").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.dataset.idx || "0");
        const w = state.warningsCache[idx];
        if (!w) return;
        const modeMap = {
          flow: "generate_flow",
          tool: "generate_tool",
          rag: "generate_rag",
          page: "generate_page",
          agent: "generate_agent",
        };
        const mode = modeMap[(w.entity_kind || "").toLowerCase()] || "explain";
        if (window.prefillAsk) {
          window.prefillAsk(
            `Explain and suggest a fix for warning ${w.code}: ${w.message} (${w.entity_kind} "${w.entity_name}")`,
            { kind: w.entity_kind, name: w.entity_name, warning: w },
            true,
            mode
          );
        }
      });
    });
  };

  consolePanel.toggleWarningsPanel = function toggleWarningsPanel(forceShow) {
    const panel = document.getElementById("warnings-panel");
    if (!panel) return;
    const shouldShow = typeof forceShow === "boolean" ? forceShow : panel.classList.contains("hidden");
    panel.classList.toggle("hidden", !shouldShow);
    if (shouldShow && (!state.warningsCache || !state.warningsCache.length)) {
      consolePanel.loadWarnings();
    }
  };

  consolePanel.loadWarnings = async function loadWarnings() {
    try {
      const data = await N.api.fetchWarnings();
      state.warningsCache = data.warnings || [];
      consolePanel.renderWarningsIndicator();
      consolePanel.renderWarningsPanel();
    } catch (err) {
      state.warningsCache = [];
      consolePanel.renderWarningsIndicator();
      consolePanel.renderWarningsPanel(`Warnings unavailable: ${err.message}`);
    }
  };
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
