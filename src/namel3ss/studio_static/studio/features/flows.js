(function (N) {
  N.features = N.features || {};
  const flows = (N.features.flows = N.features.flows || {});
  let ctx = null;

  function getState() {
    return (ctx && ctx.state) || N.state || {};
  }

  function getUtils() {
    return (ctx && ctx.utils) || N.utils || {};
  }

  async function loadStudioFlows() {
    const state = getState();
    const utils = getUtils();
    const select = document.getElementById("flow-runner-name");
    const output = document.getElementById("flow-runner-output");
    if (!select) return;
    if (output) output.textContent = "Loading flows…";
    try {
      const data = await N.api.jsonRequest("/api/studio/flows");
      const flowsList = data.flows || [];
      if (!flowsList.length) {
        select.innerHTML = '<option value="">No flows found</option>';
        if (output) output.textContent = "No flows found in the current program.";
        return;
      }
      select.innerHTML = flowsList
        .map((f) => `<option value="${utils.escapeHtml(f.name)}">${utils.escapeHtml(f.name)}${f.steps ? ` (${f.steps} steps)` : ""}</option>`)
        .join("");
      if (state.pendingRunnerFlow && flowsList.some((f) => f.name === state.pendingRunnerFlow)) {
        select.value = state.pendingRunnerFlow;
        state.pendingRunnerFlow = null;
      }
      if (output) output.textContent = "Select a flow to run.";
    } catch (err) {
      if (output) output.textContent = `Could not load flows: ${err.message}`;
      if (typeof window.setStatus === "function") window.setStatus("Error loading flows.", true);
    }
  }

  function renderFlowRunResult(result) {
    const state = getState();
    const utils = getUtils();
    const container = document.getElementById("flow-runner-output");
    if (!container) return;
    if (!result) {
      container.textContent = "No result.";
      return;
    }
    const hasErrors = (result.errors || []).length > 0 || result.success === false;
    const steps = result.steps || [];
    const durations = steps.map((s) => s.duration_seconds || 0);
    const sortedDur = [...durations].sort((a, b) => a - b);
    const slowThreshold = sortedDur.length ? sortedDur[Math.max(0, Math.floor(sortedDur.length * 0.8) - 1)] : Infinity;

    let html = `<div class="flow-run-summary ${hasErrors ? "error" : "ok"}">Flow "${utils.escapeHtml(result.flow || "")}" ${
      hasErrors ? "finished with errors" : "completed"
    }</div>`;
    html += `<div class="flow-run-summary">Run at ${utils.escapeHtml(N.utils.formatTimestamp(new Date().toISOString()))}${
      result.session_id ? ` • Session ${utils.escapeHtml(result.session_id)}` : ""
    }</div>`;
    if (result.errors && result.errors.length) {
      html += `<div class="flow-run-errors">${result.errors.map((e) => `<div>${utils.escapeHtml(e)}</div>`).join("")}</div>`;
    }
    if (steps.length) {
      html += '<div class="timeline">';
      steps.forEach((step) => {
        const statusCls = step.success === false ? "error" : "success";
        const target = step.target ? ` → ${utils.escapeHtml(step.target)}` : "";
        const duration = N.utils.formatDurationSeconds(step.duration_seconds);
        const preview = step.output_preview ? `<div class="preview">${utils.escapeHtml(step.output_preview)}</div>` : "";
        const err = step.error ? `<div class="preview">Error: ${utils.escapeHtml(step.error)}</div>` : "";
        const aiId = step.ai_id || (step.kind === "ai" ? step.target : "");
        const memoryLink =
          step.memory_kinds_used && step.memory_kinds_used.length
            ? `<button class="reload memory-link" data-ai="${utils.escapeHtml(aiId || "")}" data-session="${utils.escapeHtml(result.session_id || "")}">View memory</button>`
            : "";
        const aiCallLink = aiId
          ? `<button class="reload ai-call-link" data-ai="${utils.escapeHtml(aiId)}" data-session="${utils.escapeHtml(result.session_id || "")}">View AI context</button>`
          : "";
        const askLink = step.error
          ? `<button class="reload ask-link" data-mode="generate_flow" data-question="${utils.escapeHtml(
              `Improve or fix step ${step.name}: ${step.error}`
            )}" data-flow="${utils.escapeHtml(result.flow || "")}">Ask Studio</button>`
          : "";
        const ragInfo = step.rag_pipeline ? `<span>RAG: ${utils.escapeHtml(step.rag_pipeline)}</span>` : "";
        const toolInfo = step.tool_method || step.tool_url ? `<span>Tool: ${utils.escapeHtml(step.tool_method || "")} ${utils.escapeHtml(step.tool_url || "")}</span>` : "";
        const slowCls = step.duration_seconds && step.duration_seconds >= slowThreshold ? "slow" : "";
        html += `<div class="timeline-step ${statusCls} ${slowCls}">
          <div class="dot"></div>
          <div class="timeline-card">
            <div class="timeline-head">
              <span>[${(step.index ?? steps.indexOf(step))}] ${utils.escapeHtml(step.kind || "step")} ${utils.escapeHtml(step.name || "")}${target}</span>
              <span class="badge ${statusCls}">${statusCls === "error" ? "Error" : "Success"}</span>
            </div>
            <div class="timeline-meta">
              ${duration ? `<span>Duration ${duration}</span>` : ""}
              ${step.cost ? `<span>Cost ${utils.escapeHtml(String(step.cost))}</span>` : ""}
              ${ragInfo}
              ${toolInfo}
              ${slowCls ? `<span class="badge slow">Slow</span>` : ""}
            </div>
            <div class="timeline-details">
              ${preview || ""}
              ${err || ""}
            </div>
            <div class="timeline-actions">
              ${aiCallLink || ""}
              ${memoryLink || ""}
              ${askLink || ""}
            </div>
          </div>
        </div>`;
      });
      html += "</div>";
    } else {
      html += "<div>No steps recorded.</div>";
    }
    const finalState =
      result.final_state && Object.keys(result.final_state).length
        ? `<details class="flow-final-state"><summary>Final state</summary><pre>${utils.escapeHtml(JSON.stringify(result.final_state, null, 2))}</pre></details>`
        : "";
    container.innerHTML = html + finalState;
    container.querySelectorAll(".memory-link").forEach((btn) => {
      btn.addEventListener("click", () => window.prefillMemory && window.prefillMemory(btn.dataset.ai, btn.dataset.session || null, true));
    });
    container.querySelectorAll(".ai-call-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        const aiId = btn.dataset.ai || "";
        const sessionId = btn.dataset.session || "";
        if (window.openAiCallVisualizer) window.openAiCallVisualizer(aiId, sessionId, true);
      });
    });
    container.querySelectorAll(".ask-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        const question = btn.dataset.question || "Explain this error.";
        if (window.prefillAsk) window.prefillAsk(question, { kind: "flow", name: result.flow, flow_run: result }, true, btn.dataset.mode || null);
      });
    });
  }

  function addRunToHistory(result) {
    const state = getState();
    const entry = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      flow: result.flow || "",
      timestamp: new Date().toISOString(),
      result,
    };
    state.flowRunHistory.unshift(entry);
    while (state.flowRunHistory.length > 5) state.flowRunHistory.pop();
    renderRunHistory();
  }

  function renderRunHistory() {
    const utils = getUtils();
    const state = getState();
    const sel = document.getElementById("flow-run-history");
    if (!sel) return;
    if (!state.flowRunHistory.length) {
      sel.innerHTML = '<option value="">No recent runs</option>';
      return;
    }
    sel.innerHTML = state.flowRunHistory
      .map(
        (entry, idx) =>
          `<option value="${entry.id}">${idx === 0 ? "Latest" : `Run ${idx + 1}`} — ${utils.escapeHtml(entry.flow)} @ ${utils.escapeHtml(
            N.utils.formatTimestamp(entry.timestamp)
          )}</option>`
      )
      .join("");
  }

  function selectHistoryRun(id) {
    const state = getState();
    const entry = state.flowRunHistory.find((e) => e.id === id);
    if (!entry) return;
    renderFlowRunResult(entry.result);
  }

  function prefillRunnerWithFlow(flowName, activate) {
    const state = getState();
    if (!flowName) return;
    state.pendingRunnerFlow = flowName;
    if (activate && typeof window.activatePanel === "function") {
      window.activatePanel("run");
    }
    const select = document.getElementById("flow-runner-name");
    if (select && select.options.length) {
      select.value = flowName;
    }
    if (typeof window.setStatus === "function") window.setStatus(`Flow "${flowName}" ready to run.`, false);
  }

  async function runStudioFlow() {
    const state = getState();
    const select = document.getElementById("flow-runner-name");
    const input = document.getElementById("flow-runner-input");
    const flowName = select ? select.value.trim() : "";
    if (!flowName) {
      renderFlowRunResult({ flow: "", success: false, errors: ["Select a flow to run."], steps: [] });
      if (typeof window.setStatus === "function") window.setStatus("Flow name is required.", true);
      return;
    }
    let statePayload = {};
    let metadataPayload = {};
    const raw = input ? input.value.trim() : "";
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object") {
          if ("state" in parsed || "metadata" in parsed) {
            statePayload = parsed.state || {};
            metadataPayload = parsed.metadata || {};
          } else {
            statePayload = parsed;
          }
        }
      } catch (err) {
        renderFlowRunResult({ flow: flowName, success: false, errors: [`Invalid JSON: ${err.message}`], steps: [] });
        if (typeof window.setStatus === "function") window.setStatus("Invalid JSON payload.", true);
        return;
      }
    }
    if (typeof window.setStatus === "function") window.setStatus(`Running flow "${flowName}"…`);
    try {
      const body = { flow: flowName };
      if (Object.keys(statePayload).length) body.state = statePayload;
      if (Object.keys(metadataPayload).length) body.metadata = metadataPayload;
      const data = await N.api.jsonRequest("/api/studio/run-flow", {
        method: "POST",
        body: JSON.stringify(body),
      });
      renderFlowRunResult(data);
      addRunToHistory(data);
      if (typeof window.setStatus === "function") window.setStatus("Flow run complete.");
      if (data.session_id) {
        state.pendingMemorySession = data.session_id;
      }
      N.api.logNote({ event: "flow_run_viewed", details: { flow: flowName, success: data.success } }).catch(() => {});
    } catch (err) {
      const fallback = { flow: flowName, success: false, errors: [err.message], steps: [] };
      renderFlowRunResult(fallback);
      addRunToHistory(fallback);
      if (typeof window.setStatus === "function") window.setStatus("Error running flow.", true);
    }
  }

  flows.init = function initFlows(context) {
    ctx = context || ctx;
    return undefined;
  };

  flows.loadStudioFlows = loadStudioFlows;
  flows.renderFlowRunResult = renderFlowRunResult;
  flows.runStudioFlow = runStudioFlow;
  flows.addRunToHistory = addRunToHistory;
  flows.renderRunHistory = renderRunHistory;
  flows.selectHistoryRun = selectHistoryRun;
  flows.prefillRunnerWithFlow = prefillRunnerWithFlow;
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
