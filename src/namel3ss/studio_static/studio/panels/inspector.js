(function (N) {
  const panels = (N.panels = N.panels || {});
  const inspector = (panels.inspector = panels.inspector || {});
  let ctx = null;

  inspector.init = function initInspector(context) {
    ctx = context || ctx;
  };

  inspector.render = function renderInspector(data) {
    const container = document.getElementById("inspector-content");
    if (!container) return;
    if (!data || data.error) {
      container.textContent = data && data.error ? data.error : "Inspector unavailable.";
      return;
    }
    const utils = (ctx && ctx.utils) || N.utils;
    const state = (ctx && ctx.state) || N.state || {};
    const relevantWarnings = (state.warningsCache || []).filter(
      (w) => (w.entity_kind || "").toLowerCase() === (data.kind || "").toLowerCase() && (w.entity_name || "") === (data.name || "")
    );
    const lines = [];
    lines.push(`[${data.kind}] ${data.name}`);
    Object.keys(data).forEach((key) => {
      if (["kind", "id", "name"].includes(key)) return;
      const val = data[key];
      if (val === undefined || val === null) return;
      if (Array.isArray(val)) {
        lines.push(`${key}: ${val.join(", ") || "(empty)"}`);
      } else if (typeof val === "object") {
        try {
          lines.push(`${key}: ${JSON.stringify(val)}`);
        } catch (err) {
          lines.push(`${key}: [object]`);
        }
      } else {
        lines.push(`${key}: ${val}`);
      }
    });
    container.textContent = lines.join("\n");
    if (relevantWarnings.length) {
      const warnBox = document.createElement("div");
      warnBox.className = "warning-box";
      const title = document.createElement("div");
      title.className = "warning-box-title";
      title.textContent = `This ${data.kind} has ${relevantWarnings.length} warning${relevantWarnings.length > 1 ? "s" : ""}.`;
      warnBox.appendChild(title);
      relevantWarnings.forEach((w) => {
        const row = document.createElement("div");
        row.className = "warning-row";
        row.innerHTML = `<div class="warning-msg">${utils.escapeHtml(w.message || "")}</div><div class="warning-meta">${utils.escapeHtml(w.code || "")}</div>`;
        const askBtn = document.createElement("button");
        askBtn.className = "reload";
        askBtn.textContent = "Ask Studio";
        askBtn.addEventListener("click", () => {
          const modeMap = {
            flow: "generate_flow",
            tool: "generate_tool",
            rag: "generate_rag",
            page: "generate_page",
            agent: "generate_agent",
            ai: "explain",
            memory: "explain",
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
        row.appendChild(askBtn);
        warnBox.appendChild(row);
      });
      container.appendChild(document.createElement("br"));
      container.appendChild(warnBox);
    }
    if (data.kind === "ai" && data.has_memory) {
      const actions = document.createElement("div");
      actions.className = "inspector-actions";
      const btn = document.createElement("button");
      btn.className = "reload";
      btn.textContent = "View memory plan";
      btn.addEventListener("click", () => window.prefillMemory && window.prefillMemory(data.name, null, true));
      actions.appendChild(btn);
      container.appendChild(document.createElement("br"));
      container.appendChild(actions);
    }
    if (data.kind === "rag") {
      const btn = document.createElement("button");
      btn.className = "reload";
      btn.textContent = "View RAG pipeline";
      btn.addEventListener("click", () => window.openRagPipeline && window.openRagPipeline(data.name || "", true));
      container.appendChild(document.createElement("br"));
      container.appendChild(btn);
    }
    if (data.kind === "ai" && data.rag_pipeline) {
      const ragBtn = document.createElement("button");
      ragBtn.className = "reload";
      ragBtn.textContent = "View RAG pipeline";
      ragBtn.addEventListener("click", () => window.openRagPipeline && window.openRagPipeline(data.rag_pipeline, true));
      container.appendChild(document.createElement("br"));
      container.appendChild(ragBtn);
    }
  };

  inspector.load = async function loadInspector(kind, name) {
    if (!kind || !name) return;
    const content = document.getElementById("inspector-content");
    if (content) content.textContent = `Loading ${kind} ${name}…`;
    try {
      const api = (ctx && ctx.api) || N.api;
      const data = await api.jsonRequest(`/api/studio/inspect?kind=${encodeURIComponent(kind)}&name=${encodeURIComponent(name)}`);
      inspector.render(data);
      if (data.kind === "flow" && window.prefillRunnerWithFlow) {
        window.prefillRunnerWithFlow(data.name, false);
      }
      if (typeof window.setStatus === "function") window.setStatus("Inspector loaded.");
    } catch (err) {
      if (content) content.textContent = `Inspector failed: ${err.message}`;
      if (typeof window.setStatus === "function") window.setStatus("Inspector failed.", true);
    }
  };

  inspector.populateEntities = function populateInspectorEntities(manifest) {
    const kindSelect = document.getElementById("inspector-kind");
    const entitySelect = document.getElementById("inspector-entity");
    if (!kindSelect || !entitySelect) return;
    const nodes = (manifest && manifest.nodes) || [];
    const grouped = {};
    nodes.forEach((n) => {
      if (!grouped[n.kind]) grouped[n.kind] = [];
      grouped[n.kind].push(n.name);
    });
    const selectedKind = kindSelect.value;
    const options = grouped[selectedKind] || [];
    entitySelect.innerHTML = options.map((name) => `<option value="${name}">${name}</option>`).join("");
  };
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
