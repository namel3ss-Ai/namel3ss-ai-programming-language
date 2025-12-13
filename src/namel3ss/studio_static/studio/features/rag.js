(function (N) {
  N.features = N.features || {};
  const rag = (N.features.rag = N.features.rag || {});
  let ctx = null;

  function getState() {
    return (ctx && ctx.state) || N.state || {};
  }

  function getUtils() {
    return (ctx && ctx.utils) || N.utils || {};
  }

  async function loadRagPipelinesList() {
    const state = getState();
    const utils = getUtils();
    const listEl = document.getElementById("rag-pipelines-list");
    if (!listEl) return;
    listEl.innerHTML = "<li>Loading pipelines…</li>";
    try {
      const data = await N.api.jsonRequest("/api/studio/rag/list");
      const pipelines = data.pipelines || [];
      state.ragPipelineCache = pipelines;
      if (!pipelines.length) {
        listEl.innerHTML = "<li>No pipelines found.</li>";
        return;
      }
      listEl.innerHTML = pipelines.map((name) => `<li data-name="${utils.escapeHtml(name)}">${utils.escapeHtml(name)}</li>`).join("");
      listEl.querySelectorAll("li").forEach((li) => {
        li.addEventListener("click", () => {
          listEl.querySelectorAll("li").forEach((n) => n.classList.remove("active"));
          li.classList.add("active");
          loadRagPipeline(li.dataset.name);
        });
      });
    } catch (err) {
      listEl.innerHTML = `<li>Error loading pipelines: ${utils.escapeHtml(err.message)}</li>`;
    }
  }

  async function loadRagPipeline(name) {
    const titleEl = document.getElementById("rag-pipeline-title");
    const stagesEl = document.getElementById("rag-pipeline-stages");
    const detailsEl = document.getElementById("rag-pipeline-details");
    if (titleEl) titleEl.textContent = name ? `Pipeline: ${name}` : "Select a pipeline to view its stages.";
    if (stagesEl) stagesEl.innerHTML = "";
    if (detailsEl) detailsEl.textContent = "";
    if (!name) return;
    try {
      const data = await N.api.jsonRequest(`/api/studio/rag/pipeline?name=${encodeURIComponent(name)}`);
      renderRagPipeline(data);
    } catch (err) {
      if (titleEl) titleEl.textContent = `Unable to load pipeline: ${err.message}`;
    }
  }

  function renderRagPipeline(manifest) {
    const utils = getUtils();
    if (!manifest) return;
    const titleEl = document.getElementById("rag-pipeline-title");
    const stagesEl = document.getElementById("rag-pipeline-stages");
    const detailsEl = document.getElementById("rag-pipeline-details");
    if (titleEl)
      titleEl.textContent = `Pipeline: ${manifest.name || ""}${manifest.default_vector_store ? ` • default store ${manifest.default_vector_store}` : ""}`;
    if (stagesEl) {
      const stages = manifest.stages || [];
      const parts = [];
      stages.forEach((stage, idx) => {
        parts.push(`<div class="rag-stage">
          <h5>${utils.escapeHtml(stage.name || `Stage ${idx + 1}`)}</h5>
          <div class="meta">
            <span>kind: ${utils.escapeHtml(stage.kind || "")}</span>
            ${stage.ai ? `<span>ai: ${utils.escapeHtml(stage.ai)}</span>` : ""}
            ${stage.vector_store ? `<span>vector_store: ${utils.escapeHtml(stage.vector_store)}</span>` : ""}
            ${stage.frame ? `<span>frame: ${utils.escapeHtml(stage.frame)}</span>` : ""}
            ${stage.graph ? `<span>graph: ${utils.escapeHtml(stage.graph)}</span>` : ""}
            ${stage.top_k ? `<span>top_k: ${utils.escapeHtml(String(stage.top_k))}</span>` : ""}
          </div>
        </div>`);
        if (idx + 1 < stages.length) {
          parts.push('<div class="rag-connector"></div>');
        }
      });
      stagesEl.innerHTML = parts.join("") || "<div>No stages defined.</div>";
    }
    if (detailsEl) {
      detailsEl.textContent = JSON.stringify(manifest, null, 2);
    }
  }

  function openRagPipeline(name, focusPanel) {
    if (!name) return;
    if (focusPanel && typeof window.activatePanel === "function") window.activatePanel("rag");
    loadRagPipeline(name);
    const list = document.getElementById("rag-pipelines-list");
    if (list) {
      list.querySelectorAll("li").forEach((li) => li.classList.toggle("active", li.dataset.name === name));
    }
  }

  async function runRagQuery() {
    const utils = getUtils();
    const query = document.getElementById("rag-query").value.trim();
    const indexesRaw = document.getElementById("rag-indexes").value.trim();
    const source = document.getElementById("rag-source").value;
    const indexes = indexesRaw ? indexesRaw.split(",").map((i) => i.trim()).filter(Boolean) : null;
    if (!query) {
      renderJsonIn("rag-content", "Query is required.");
      if (typeof window.setStatus === "function") window.setStatus("Query is required.", true);
      return;
    }
    if (typeof window.setStatus === "function") window.setStatus("Running RAG query…");
    try {
      const body = { query, code: source };
      if (indexes && indexes.length) {
        body.indexes = indexes;
      }
      const data = await N.api.jsonRequest("/api/rag/query", {
        method: "POST",
        body: JSON.stringify(body),
      });
      renderJsonIn("rag-content", data);
      if (typeof window.setStatus === "function") window.setStatus("RAG query complete.");
    } catch (err) {
      console.error(err);
      renderJsonIn("rag-content", `Error: ${err.message}`);
      if (typeof window.setStatus === "function") window.setStatus("Error running RAG query.", true);
    }
  }

  function renderJsonIn(elementId, data) {
    if (typeof window.renderJsonIn === "function") return window.renderJsonIn(elementId, data);
  }

  rag.init = function initRag(context) {
    ctx = context || ctx;
    return undefined;
  };

  rag.loadRagPipelinesList = loadRagPipelinesList;
  rag.loadRagPipeline = loadRagPipeline;
  rag.renderRagPipeline = renderRagPipeline;
  rag.openRagPipeline = openRagPipeline;
  rag.runRagQuery = runRagQuery;
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
