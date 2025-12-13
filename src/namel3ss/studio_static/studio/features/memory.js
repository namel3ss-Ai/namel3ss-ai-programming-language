(function (N) {
  N.features = N.features || {};
  const memory = (N.features.memory = N.features.memory || {});
  let ctx = null;

  function getApi() {
    return (ctx && ctx.api) || N.api;
  }

  function prefillMemory(aiId, sessionId = null, activate = false) {
    const state = (ctx && ctx.state) || N.state;
    if (!aiId) return;
    state.pendingMemoryAi = aiId;
    state.pendingMemorySession = sessionId;
    if (activate && typeof window.activatePanel === "function") {
      window.activatePanel("memory");
    }
    const select = document.getElementById("memory-ai-select");
    if (select && select.options.length) {
      select.value = aiId;
      loadMemoryDetails(aiId);
    }
  }

  function renderMemoryPlan(plan) {
    const utils = (ctx && ctx.utils) || N.utils;
    const container = document.getElementById("memory-plan");
    if (!container) return;
    if (!plan || plan.has_memory === false) {
      container.textContent = "This AI has no memory configured.";
      return;
    }
    const kinds = plan.kinds || [];
    const rows = kinds
      .map(
        (k) =>
          `<tr><td>${utils.escapeHtml(k.kind)}</td><td>${k.enabled ? "enabled" : "disabled"}</td><td>${k.scope || ""}</td><td>${k.store || ""}</td><td>${k.window || k.retention_days || ""}</td><td>${k.pii_policy || ""}</td></tr>`
      )
      .join("");
    const recallRows = (plan.recall || [])
      .map(
        (r) =>
          `<tr><td>${utils.escapeHtml(r.source || "")}</td><td>${r.count || ""}</td><td>${r.top_k || ""}</td><td>${r.include === false ? "skip" : "include"}</td></tr>`
      )
      .join("");
    container.innerHTML = `
      <div class="memory-context-section">
        <h4>Memory plan</h4>
        <table class="memory-plan-table">
          <thead><tr><th>Kind</th><th>Status</th><th>Scope</th><th>Store</th><th>Window/Retention</th><th>PII</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='6'>No memory kinds</td></tr>"}</tbody>
        </table>
      </div>
      <div class="memory-context-section">
        <h4>Recall rules</h4>
        <table class="memory-recall-table">
          <thead><tr><th>Source</th><th>Count</th><th>Top K</th><th>Include</th></tr></thead>
          <tbody>${recallRows || "<tr><td colspan='4'>No recall rules</td></tr>"}</tbody>
        </table>
      </div>
    `;
  }

  function renderMemorySessions(aiId, sessions) {
    const utils = (ctx && ctx.utils) || N.utils;
    const state = (ctx && ctx.state) || N.state;
    const container = document.getElementById("memory-sessions");
    if (!container) return;
    if (!sessions || !sessions.length) {
      container.textContent = "No sessions found yet for this AI. Run a flow to create one.";
      return;
    }
    const items = sessions
      .map(
        (s) =>
          `<li data-session="${utils.escapeHtml(s.id || s.session_id || "")}"><strong>${utils.escapeHtml(
            s.id || s.session_id || "(unknown)"
          )}</strong><br><small>turns: ${s.turns ?? "-"}${s.user_id ? ` • user: ${utils.escapeHtml(s.user_id)}` : ""}</small></li>`
      )
      .join("");
    container.innerHTML = `<div class="memory-context-section"><h4>Sessions</h4><ul class="memory-sessions-list">${items}</ul></div>`;
    container.querySelectorAll("li[data-session]").forEach((el) => {
      el.addEventListener("click", () => {
        container.querySelectorAll("li").forEach((li) => li.classList.remove("active"));
        el.classList.add("active");
        loadMemoryState(aiId, el.dataset.session);
      });
      if (state.pendingMemorySession && el.dataset.session === state.pendingMemorySession) {
        el.click();
        state.pendingMemorySession = null;
      }
    });
  }

  function renderTurns(turns) {
    const utils = (ctx && ctx.utils) || N.utils;
    if (!turns || !turns.length) return "<div>No short-term history.</div>";
    return turns
      .map((t) => {
        const role = (t.role || "assistant").toLowerCase();
        return `<div class="memory-message ${role}"><strong>${utils.escapeHtml(role)}</strong>: ${utils.escapeHtml(t.content || "")}</div>`;
      })
      .join("");
  }

  function renderItems(items) {
    const utils = (ctx && ctx.utils) || N.utils;
    if (!items || !items.length) return "<div>No entries.</div>";
    return items
      .map((item) => {
        if (typeof item === "string") {
          return `<div class="memory-message">${utils.escapeHtml(item)}</div>`;
        }
        return `<div class="memory-message"><strong>${utils.escapeHtml(item.kind || item.source || "")}</strong>: ${utils.escapeHtml(item.content || item.text || JSON.stringify(item))}</div>`;
      })
      .join("");
  }

  function renderRecallSnapshot(snapshot) {
    const utils = (ctx && ctx.utils) || N.utils;
    if (!snapshot) return "<div>No recall snapshot.</div>";
    const msgs = (snapshot.messages || []).map((m) => `<div class="memory-message ${utils.escapeHtml(m.role || "")}"><strong>${utils.escapeHtml(m.role || "")}</strong>: ${utils.escapeHtml(m.content || "")}</div>`).join("");
    const diags = (snapshot.diagnostics || []).map((d) => `<div>${utils.escapeHtml(d.source || "")} → selected ${d.selected_count || d.count || 0}</div>`).join("");
    return `
      <div class="memory-context-section">
        <h4>Recall messages (${snapshot.messages ? snapshot.messages.length : 0})</h4>
        ${msgs || "<div>No messages.</div>"}
      </div>
      <div class="memory-context-section">
        <h4>Diagnostics</h4>
        ${diags || "<div>No diagnostics.</div>"}
      </div>
    `;
  }

  function renderMemoryState(payload) {
    const utils = (ctx && ctx.utils) || N.utils;
    const container = document.getElementById("memory-state");
    if (!container) return;
    if (!payload) {
      container.textContent = "Select a session to view context.";
      return;
    }
    const kinds = payload.kinds || {};
    const shortHtml = kinds.short_term ? renderTurns(kinds.short_term.turns) : "<div>No short-term history.</div>";
    const longHtml = kinds.long_term ? renderItems(kinds.long_term.items) : "<div>No long-term items.</div>";
    const profileHtml = kinds.profile ? renderItems(kinds.profile.facts) : "<div>No profile facts.</div>";
    const episodicHtml = kinds.episodic ? renderItems(kinds.episodic.items) : "<div>No episodic items.</div>";
    const semanticHtml = kinds.semantic ? renderItems(kinds.semantic.items) : "<div>No semantic items.</div>";
    const recallHtml = renderRecallSnapshot(payload.recall_snapshot);
    container.innerHTML = `
      <div class="memory-context-section"><h4>Session</h4><div>session: ${utils.escapeHtml(payload.session_id || "")}${payload.user_id ? ` • user: ${utils.escapeHtml(payload.user_id)}` : ""}</div></div>
      <div class="memory-context-section"><h4>Short-term</h4>${shortHtml}</div>
      <div class="memory-context-section"><h4>Long-term</h4>${longHtml}</div>
      <div class="memory-context-section"><h4>Profile</h4>${profileHtml}</div>
      <div class="memory-context-section"><h4>Episodic</h4>${episodicHtml}</div>
      <div class="memory-context-section"><h4>Semantic</h4>${semanticHtml}</div>
      ${recallHtml}
      <div class="memory-context-section memory-actions">
        <button class="reload ask-link" data-ai="${utils.escapeHtml(payload.ai || "")}" data-session="${utils.escapeHtml(payload.session_id || "")}">Ask Studio about this memory</button>
        <button class="reload ai-call-link" data-ai="${utils.escapeHtml(payload.ai || "")}" data-session="${utils.escapeHtml(payload.session_id || "")}">View AI call context</button>
      </div>
    `;
    container.querySelectorAll(".ask-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        const aiId = btn.dataset.ai || "";
        const sessionId = btn.dataset.session || "";
        if (typeof window.prefillAsk === "function") {
          window.prefillAsk(`Help me understand memory state for ${aiId}.`, { kind: "ai", ai_id: aiId, session_id: sessionId }, true);
        }
      });
    });
    container.querySelectorAll(".ai-call-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        const aiId = btn.dataset.ai || "";
        const sessionId = btn.dataset.session || "";
        if (typeof window.openAiCallVisualizer === "function") {
          window.openAiCallVisualizer(aiId, sessionId, true);
        }
      });
    });
  }

  function renderMemoryPlanRaw(payload) {
    if (typeof window.renderJsonIn === "function") {
      window.renderJsonIn("memory-plan", payload ? JSON.stringify(payload, null, 2) : "");
    }
  }

  function renderMemorySessionsRaw(payload) {
    if (typeof window.renderJsonIn === "function") {
      window.renderJsonIn("memory-sessions", payload ? JSON.stringify(payload, null, 2) : "");
    }
  }

  function renderMemoryStateRaw(payload) {
    if (typeof window.renderJsonIn === "function") {
      window.renderJsonIn("memory-state", payload ? JSON.stringify(payload, null, 2) : "");
    }
  }

  function renderAiCall(payload) {
    const utils = (ctx && ctx.utils) || N.utils;
    const metaEl = document.getElementById("ai-call-meta");
    const sectionsEl = document.getElementById("ai-call-sections");
    if (!metaEl || !sectionsEl) return;
    if (!payload) {
      metaEl.textContent = "No AI call data.";
      sectionsEl.innerHTML = "";
      return;
    }
    metaEl.innerHTML = `<strong>${utils.escapeHtml(payload.ai_id || "")}</strong> • model ${utils.escapeHtml(payload.model || "")} • session ${utils.escapeHtml(payload.session_id || "")}${payload.timestamp ? ` • ${utils.escapeHtml(payload.timestamp)}` : ""}`;
    const messages = (payload.messages || []).map(
      (m) =>
        `<div class="ai-call-message"><div class="role">${utils.escapeHtml(m.role || "")}${m.kind ? ` • ${utils.escapeHtml(m.kind)}` : ""}</div><div>${utils.escapeHtml(m.content || "")}</div></div>`
    ).join("");
    const ragMatches = (payload.rag?.matches || [])
      .map((m) => `<div class="ai-call-message"><div class="role">RAG</div><div>${utils.escapeHtml(m.text || "")}<br><small>${utils.escapeHtml(m.source || "")} • score ${m.score ?? ""}</small></div></div>`)
      .join("");
    const diagnosticsRows = (payload.recall_diagnostics || [])
      .map((d) => `<tr><td>${utils.escapeHtml(d.source || "")}</td><td>${utils.escapeHtml(d.scope || "")}</td><td>${utils.escapeHtml(String(d.selected_count ?? d.count ?? ""))}</td><td>${utils.escapeHtml(String(d.limit ?? ""))}</td></tr>`)
      .join("");
    const ragLink = payload.rag_pipeline ? `<button class="reload" onclick="return false;" id="ai-rag-link">View RAG pipeline</button>` : "";
    const diagnosticsRowsHtml = diagnosticsRows || "<tr><td colspan='4'>No diagnostics.</td></tr>";
    sectionsEl.innerHTML = `
      <div class="ai-call-section">
        <h4>Messages</h4>
        <div>${messages || "No messages."}</div>
      </div>
      <div class="ai-call-section">
        <h4>Recall diagnostics</h4>
        <table class="ai-call-table">
          <thead><tr><th>Source</th><th>Scope</th><th>Selected</th><th>Limit</th></tr></thead>
          <tbody>${diagnosticsRowsHtml}</tbody>
        </table>
      </div>
      <div class="ai-call-section">
        <h4>RAG matches</h4>
        <div>${ragMatches || "No RAG matches."}</div>
      </div>
      ${ragLink ? `<div class="ai-call-section">${ragLink}</div>` : ""}
    `;
    if (payload.rag_pipeline) {
      const btn = document.getElementById("ai-rag-link");
      if (btn) {
        btn.addEventListener("click", () => {
          if (typeof window.openRagPipeline === "function") {
            window.openRagPipeline(payload.rag_pipeline, true);
          }
        });
      }
    }
  }

  async function loadAiCall(aiId, sessionId) {
    const metaEl = document.getElementById("ai-call-meta");
    const sectionsEl = document.getElementById("ai-call-sections");
    if (metaEl) metaEl.textContent = "Loading AI call…";
    if (sectionsEl) sectionsEl.innerHTML = "";
    if (!aiId || !sessionId) {
      if (metaEl) metaEl.textContent = "Select an AI call from Run or Memory panels.";
      return;
    }
    try {
      const data = await getApi().jsonRequest(`/api/studio/ai-call?ai=${encodeURIComponent(aiId)}&session=${encodeURIComponent(sessionId)}`);
      renderAiCall(data);
      const state = (ctx && ctx.state) || N.state;
      state.pendingAiCall = null;
      if (typeof window.setStatus === "function") window.setStatus("AI call loaded.");
    } catch (err) {
      if (metaEl) metaEl.textContent = `Unable to load AI call: ${err.message}`;
      if (typeof window.setStatus === "function") window.setStatus("AI call load failed.", true);
    }
  }

  function openAiCallVisualizer(aiId, sessionId, focusPanel = false) {
    const state = (ctx && ctx.state) || N.state;
    state.pendingAiCall = { ai: aiId, session: sessionId };
    if (focusPanel && typeof window.activatePanel === "function") {
      window.activatePanel("ai-call");
    }
    if (document.getElementById("panel-ai-call")?.classList.contains("active")) {
      loadAiCall(aiId, sessionId);
    }
  }

  async function loadMemoryDetails(aiId) {
    if (!aiId) return;
    try {
      const [plan, sessions] = await Promise.all([
        getApi().jsonRequest(`/api/memory/ai/${encodeURIComponent(aiId)}/plan`),
        getApi().jsonRequest(`/api/memory/ai/${encodeURIComponent(aiId)}/sessions`),
      ]);
      renderMemoryPlan(plan);
      renderMemorySessions(aiId, sessions.sessions || sessions.session || sessions || []);
    } catch (err) {
      renderJsonIn("memory-plan", `Error loading memory: ${err.message}`);
      renderJsonIn("memory-sessions", "Unable to load sessions.");
      if (typeof window.setStatus === "function") window.setStatus("Error loading memory.", true);
    }
  }

  async function loadMemoryState(aiId, sessionId) {
    if (!aiId || !sessionId) {
      renderMemoryState(null);
      return;
    }
    try {
      const payload = await getApi().jsonRequest(`/api/memory/ai/${encodeURIComponent(aiId)}/state?session_id=${encodeURIComponent(sessionId)}`);
      renderMemoryState(payload);
      if (typeof window.setStatus === "function") window.setStatus("Memory state loaded.");
    } catch (err) {
      renderJsonIn("memory-state", `Error loading memory state: ${err.message}`);
      if (typeof window.setStatus === "function") window.setStatus("Error loading memory state.", true);
    }
  }

  async function loadMemoryAIs() {
    const utils = (ctx && ctx.utils) || N.utils;
    const state = (ctx && ctx.state) || N.state;
    const select = document.getElementById("memory-ai-select");
    const planContainer = document.getElementById("memory-plan");
    if (!select) return;
    select.innerHTML = '<option value="">Loading…</option>';
    try {
      const data = await getApi().jsonRequest("/api/memory/ais");
      const ais = data.ais || [];
      if (!ais.length) {
        select.innerHTML = '<option value="">No AIs with memory</option>';
        if (planContainer) planContainer.textContent = "No AIs with memory configured in this program.";
        return;
      }
      select.innerHTML = ais.map((a) => `<option value="${utils.escapeHtml(a.id)}">${utils.escapeHtml(a.name || a.id)}</option>`).join("");
      const desired = state.pendingMemoryAi && ais.some((a) => a.id === state.pendingMemoryAi) ? state.pendingMemoryAi : select.value;
      if (desired) {
        select.value = desired;
        state.pendingMemoryAi = null;
        await loadMemoryDetails(desired);
        if (state.pendingMemorySession) {
          await loadMemoryState(desired, state.pendingMemorySession);
          state.pendingMemorySession = null;
        }
      }
      select.addEventListener("change", async () => {
        const aiId = select.value;
        if (!aiId) return;
        await loadMemoryDetails(aiId);
      });
    } catch (err) {
      select.innerHTML = '<option value="">Error loading AIs</option>';
      if (planContainer) planContainer.textContent = "";
      if (typeof window.renderJsonIn === "function") window.renderJsonIn("memory-plan", `Error: ${err.message}`);
      if (typeof window.setStatus === "function") window.setStatus("Error loading memory AIs.", true);
    }
  }

  function loadMemory() {
    loadMemoryAIs();
    if (typeof window.setStatus === "function") window.setStatus("Memory panel ready.");
  }

  function initMemory(context) {
    ctx = context || ctx;
    return undefined;
  }

  memory.prefillMemory = prefillMemory;
  memory.renderMemoryPlan = renderMemoryPlan;
  memory.renderMemorySessions = renderMemorySessions;
  memory.renderMemoryState = renderMemoryState;
  memory.renderMemoryPlanRaw = renderMemoryPlanRaw;
  memory.renderMemorySessionsRaw = renderMemorySessionsRaw;
  memory.renderMemoryStateRaw = renderMemoryStateRaw;
  memory.renderAiCall = renderAiCall;
  memory.loadAiCall = loadAiCall;
  memory.openAiCallVisualizer = openAiCallVisualizer;
  memory.renderTurns = renderTurns;
  memory.renderItems = renderItems;
  memory.renderRecallSnapshot = renderRecallSnapshot;
  memory.loadMemoryDetails = loadMemoryDetails;
  memory.loadMemoryState = loadMemoryState;
  memory.loadMemoryAIs = loadMemoryAIs;
  memory.loadMemory = loadMemory;
  memory.init = initMemory;
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
