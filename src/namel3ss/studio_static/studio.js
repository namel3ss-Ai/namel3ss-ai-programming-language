(() => {
  const loadedPanels = new Set();
  let pendingRunnerFlow = null;
  let pendingMemoryAi = null;
  let pendingMemorySession = null;
  let pendingAskContext = null;
  let currentTheme = "light";
  let pendingAiCall = null;
  const flowRunHistory = [];
  let commandPaletteOpen = false;
  let commandItems = [];
  let commandFiltered = [];
  let commandSelectedIndex = 0;
  let ragPipelineCache = [];
  let canvasScale = 1;
  let canvasOffset = { x: 0, y: 0 };
  let isCanvasPanning = false;
  let canvasPanStart = { x: 0, y: 0 };
  let canvasViewport = null;
  let canvasGroupsEl = null;
  let presentationMode = false;
  let askMode = "explain";
  let warningsCache = [];
  const CANVAS_KIND_ORDER = ["app", "page", "flow", "ai", "agent", "tool", "memory", "rag", "rag_eval", "tool_eval", "agent_eval", "model", "vector_store"];
  const CANVAS_KIND_LABELS = {
    app: "Apps",
    page: "Pages",
    flow: "Flows",
    ai: "AI Calls",
    agent: "Agents",
    tool: "Tools",
    memory: "Memory",
    model: "Models",
    rag: "RAG Pipelines",
    vector_store: "Vector Stores",
    rag_eval: "RAG Evals",
    tool_eval: "Tool Evals",
    agent_eval: "Agent Evals",
  };
  const CANVAS_NODE_SIZES = {
    app: { width: 240, height: 112 },
    page: { width: 230, height: 102 },
    flow: { width: 230, height: 110 },
    ai: { width: 230, height: 102 },
    agent: { width: 220, height: 96 },
    tool: { width: 220, height: 94 },
    memory: { width: 220, height: 94 },
    rag: { width: 240, height: 112 },
    rag_eval: { width: 220, height: 94 },
    tool_eval: { width: 220, height: 94 },
    agent_eval: { width: 220, height: 94 },
    model: { width: 220, height: 92 },
    vector_store: { width: 220, height: 92 },
    default: { width: 210, height: 90 },
  };

  function getApiKey() {
    const el = document.getElementById("api-key-input");
    return el ? el.value.trim() : "";
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setStatus(message, isError = false) {
    const el = document.getElementById("studio-status");
    if (!el) return;
    el.textContent = message;
    el.classList.toggle("status-error", Boolean(isError));
  }

  function clamp(val, min, max) {
    return Math.min(Math.max(val, min), max);
  }

  function formatLogLine(entry) {
    const ts = entry.timestamp || "";
    const level = entry.level || "info";
    const event = entry.event || "";
    const details = entry.details || {};
    let detailText = "";
    try {
      detailText = Object.entries(details)
        .map(([k, v]) => `${k}=${v}`)
        .join("  ");
    } catch (err) {
      detailText = "";
    }
    return { ts, level, event, detailText };
  }

  function renderLogs(entries) {
    const container = document.getElementById("logs-content");
    if (!container) return;
    if (!entries || !entries.length) {
      container.innerHTML = "<div class=\"log-entry\">No logs yet.</div>";
      return;
    }
    const html = entries
      .map((entry) => {
        const { ts, level, event, detailText } = formatLogLine(entry);
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
  }

  function connectLogsStream() {
    const container = document.getElementById("logs-content");
    if (!container) return;
    const entries = [];
    function push(entry) {
      entry.__fresh = true;
      entries.push(entry);
      if (entries.length > 300) entries.shift();
      renderLogs(entries);
    }
    fetch("/api/studio/logs/stream")
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
  }

  function formatDurationSeconds(value) {
    if (value == null) return "";
    if (value < 0.001) return `${Math.round(value * 1e6)} µs`;
    if (value < 1) return `${Math.round(value * 1000)} ms`;
    return `${value.toFixed(2)} s`;
  }

  function formatTimestamp(ts) {
    if (!ts) return "";
    try {
      return new Date(ts).toLocaleTimeString();
    } catch (err) {
      return ts;
    }
  }

  function canvasNodeSize(kind) {
    return CANVAS_NODE_SIZES[kind] || CANVAS_NODE_SIZES.default;
  }

  function canvasLerp(a, b, t) {
    if (!Number.isFinite(a)) return b;
    return a + (b - a) * t;
  }

  function canvasHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i += 1) {
      hash = (hash * 31 + str.charCodeAt(i)) | 0;
    }
    return Math.abs(hash);
  }

  function canvasManifestSignature(manifest) {
    const ids = ((manifest && manifest.nodes) || []).map((n) => n.id || "").sort().join("|");
    const edges = ((manifest && manifest.edges) || [])
      .map((e) => `${e.from || ""}>${e.to || ""}:${e.kind || ""}`)
      .sort()
      .join("|");
    return `${canvasHash(ids)}-${canvasHash(edges)}-${(manifest && manifest.nodes ? manifest.nodes.length : 0)}`;
  }

  function canvasProjectKey() {
    const path = (window.location && window.location.pathname) || "namel3ss";
    const host = (window.location && window.location.host) || "local";
    return `n3_canvas_layout_v1_${host}_${path}`.replace(/[^a-z0-9:_-]/gi, "_");
  }

  function readCanvasLayoutCache(projectKey) {
    try {
      const raw = localStorage.getItem(projectKey);
      if (!raw) return { signature: null, nodes: {} };
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        return { signature: parsed.signature || null, nodes: parsed.nodes || {} };
      }
    } catch (err) {
      // ignore cache errors
    }
    return { signature: null, nodes: {} };
  }

  function writeCanvasLayoutCache(projectKey, signature, nodes) {
    try {
      localStorage.setItem(projectKey, JSON.stringify({ signature, nodes, layout_version: 1 }));
    } catch (err) {
      // ignore cache write errors
    }
  }

  function applyCanvasTransform() {
    if (!canvasGroupsEl) return;
    canvasGroupsEl.style.transform = `translate(${canvasOffset.x}px, ${canvasOffset.y}px) scale(${canvasScale})`;
  }

  function handleCanvasWheel(event) {
    if (!canvasViewport || !canvasGroupsEl) return;
    event.preventDefault();
    const rect = canvasViewport.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const prevScale = canvasScale;
    const scaleDelta = Math.exp(-event.deltaY * 0.0012);
    canvasScale = clamp(canvasScale * scaleDelta, 0.6, 1.8);
    const factor = canvasScale / prevScale;
    canvasOffset.x = px - (px - canvasOffset.x) * factor;
    canvasOffset.y = py - (py - canvasOffset.y) * factor;
    applyCanvasTransform();
  }

  function handleCanvasMouseDown(event) {
    if (!canvasViewport) return;
    isCanvasPanning = true;
    canvasPanStart = { x: event.clientX - canvasOffset.x, y: event.clientY - canvasOffset.y };
    canvasViewport.style.cursor = "grabbing";
  }

  function handleCanvasMouseMove(event) {
    if (!isCanvasPanning) return;
    canvasOffset.x = event.clientX - canvasPanStart.x;
    canvasOffset.y = event.clientY - canvasPanStart.y;
    applyCanvasTransform();
  }

  function handleCanvasMouseUp() {
    if (!canvasViewport) return;
    isCanvasPanning = false;
    canvasViewport.style.cursor = "grab";
  }

  function focusCanvasOnNode(nodeEl) {
    if (!canvasViewport || !nodeEl) return;
    const viewportRect = canvasViewport.getBoundingClientRect();
    const nodeRect = nodeEl.getBoundingClientRect();
    const targetX = viewportRect.left + viewportRect.width / 2 - (nodeRect.left + nodeRect.width / 2);
    const targetY = viewportRect.top + viewportRect.height / 2 - (nodeRect.top + nodeRect.height / 2);
    canvasOffset.x += targetX;
    canvasOffset.y += targetY;
    applyCanvasTransform();
  }

  function initCanvasInteractions() {
    if (canvasViewport && canvasGroupsEl) return;
    canvasViewport = document.getElementById("canvas-viewport");
    canvasGroupsEl = document.getElementById("canvas-groups");
    if (!canvasViewport || !canvasGroupsEl) return;
    canvasViewport.addEventListener("wheel", handleCanvasWheel, { passive: false });
    canvasViewport.addEventListener("mousedown", handleCanvasMouseDown);
    window.addEventListener("mousemove", handleCanvasMouseMove);
    window.addEventListener("mouseup", handleCanvasMouseUp);
    window.addEventListener("mouseleave", handleCanvasMouseUp);
    applyCanvasTransform();
  }

  function resolveCanvasCollisions(columns, gap, topPadding) {
    columns.forEach((col) => {
      const sorted = [...col.nodes].sort((a, b) => {
        if (a.y === b.y) {
          return (a.name || "").localeCompare(b.name || "") || (a.id || "").localeCompare(b.id || "");
        }
        return a.y - b.y;
      });
      let cursor = topPadding;
      sorted.forEach((node) => {
        if (!Number.isFinite(node.y)) node.y = cursor;
        node.y = Math.max(node.y, cursor);
        cursor = node.y + node.height + gap;
      });
    });
  }

  function applyCanvasBarycenter(columns, edges, nodeById, mode) {
    const ordered = mode === "children" ? [...columns].reverse() : columns;
    ordered.forEach((col, idx) => {
      if (idx === 0) return;
      col.nodes.forEach((node) => {
        const neighborIndex = mode === "parents" ? node.columnIndex - 1 : node.columnIndex + 1;
        const neighbors = edges
          .filter((edge) => {
            if (mode === "parents") {
              return edge.to === node.id && nodeById[edge.from] && nodeById[edge.from].columnIndex === neighborIndex;
            }
            return edge.from === node.id && nodeById[edge.to] && nodeById[edge.to].columnIndex === neighborIndex;
          })
          .map((edge) => nodeById[mode === "parents" ? edge.from : edge.to]);
        if (!neighbors.length) return;
        const avgCenter = neighbors.reduce((sum, n) => sum + (n.y + n.height / 2), 0) / neighbors.length;
        const desiredTop = avgCenter - node.height / 2;
        node.y = canvasLerp(node.y, desiredTop, 0.65);
      });
    });
  }

  function computeCanvasLayout(manifest) {
    const nodesRaw = (manifest.nodes || []).map((node) => {
      const kind = node.kind || "other";
      const size = canvasNodeSize(kind);
      return {
        ...node,
        kind,
        width: size.width,
        height: size.height,
      };
    });
    const edges = manifest.edges || [];
    const projectKey = canvasProjectKey();
    const manifestSig = canvasManifestSignature(manifest);
    const cached = readCanvasLayoutCache(projectKey);
    const cachedNodes = cached.nodes || {};
    const kindsPresent = new Set(nodesRaw.map((n) => n.kind || "other"));
    const columnKinds = [
      ...CANVAS_KIND_ORDER.filter((k) => kindsPresent.has(k)),
      ...[...kindsPresent].filter((k) => !CANVAS_KIND_ORDER.includes(k)).sort(),
    ];
    if (!columnKinds.length) {
      const emptyHeight = presentationMode ? 420 : 340;
      return { nodes: [], columns: [], width: 0, height: emptyHeight };
    }
    const columnIndex = {};
    columnKinds.forEach((kind, idx) => {
      columnIndex[kind] = idx;
    });
    const columnWidth = 240;
    const columnGap = presentationMode ? 220 : 180;
    const rowGap = presentationMode ? 30 : 22;
    const topPadding = presentationMode ? 52 : 40;
    const sidePadding = 48;
    const minHeight = presentationMode ? 420 : 340;
    const nodes = nodesRaw
      .sort((a, b) => {
        const kindOrder = (columnIndex[a.kind] ?? 0) - (columnIndex[b.kind] ?? 0);
        if (kindOrder !== 0) return kindOrder;
        const nameOrder = (a.name || "").localeCompare(b.name || "");
        if (nameOrder !== 0) return nameOrder;
        return (a.id || "").localeCompare(b.id || "");
      })
      .map((node) => {
        const kind = node.kind || "other";
        const col = columnIndex[kind] ?? columnKinds.length;
        const cachedPos = cachedNodes[node.id] || {};
        return {
          ...node,
          kind,
          columnIndex: col,
          x: sidePadding + col * (columnWidth + columnGap) + (columnWidth - node.width) / 2,
          y: Number.isFinite(cachedPos.y) ? cachedPos.y : NaN,
        };
      });
    const nodeById = {};
    nodes.forEach((n) => {
      nodeById[n.id] = n;
    });
    const columns = columnKinds
      .map((kind) => ({
        kind,
        columnIndex: columnIndex[kind],
        nodes: nodes.filter((n) => n.kind === kind),
        x: sidePadding + (columnIndex[kind] || 0) * (columnWidth + columnGap),
      }))
      .filter((col) => col.nodes.length);

    columns.forEach((col) => {
      let cursor = topPadding;
      col.nodes.forEach((node) => {
        if (!Number.isFinite(node.y)) {
          node.y = cursor;
          cursor += node.height + rowGap;
        }
      });
    });

    edges.forEach((edge) => {
      if (edge.kind === "entry_page" && nodeById[edge.from] && nodeById[edge.to]) {
        const appNode = nodeById[edge.from];
        const pageNode = nodeById[edge.to];
        pageNode.y = Math.min(pageNode.y, appNode.y + 12);
      }
    });

    applyCanvasBarycenter(columns, edges, nodeById, "parents");
    resolveCanvasCollisions(columns, rowGap, topPadding);
    applyCanvasBarycenter(columns, edges, nodeById, "children");
    resolveCanvasCollisions(columns, rowGap, topPadding);
    resolveCanvasCollisions(columns, rowGap, topPadding);

    const maxX = nodes.reduce((acc, n) => Math.max(acc, n.x + n.width), 0);
    const maxY = nodes.reduce((acc, n) => Math.max(acc, n.y + n.height), 0);
    const layoutSpan = columnKinds.length ? sidePadding * 2 + columnKinds.length * columnWidth + (columnKinds.length - 1) * columnGap : 0;
    const width = Math.max(maxX + sidePadding, layoutSpan);
    const height = Math.max(maxY + topPadding, minHeight);
    const layoutNodes = {};
    nodes.forEach((n) => {
      layoutNodes[n.id] = { x: n.x, y: n.y, width: n.width, height: n.height };
    });
    writeCanvasLayoutCache(projectKey, manifestSig, layoutNodes);

    const columnsMeta = columns.map((col) => ({
      kind: col.kind,
      x: col.x,
      width: columnWidth,
    }));

    return { nodes, columns: columnsMeta, width, height };
  }

  function renderCanvas(manifest) {
    initCanvasInteractions();
    const groupsEl = document.getElementById("canvas-groups");
    const detailsEl = document.getElementById("canvas-details");
    if (!groupsEl || !detailsEl) return;
    canvasGroupsEl = groupsEl;
    window.n3CanvasManifest = manifest;
    groupsEl.innerHTML = "";
    const selectedCls = "selected";
    let selectedId = null;
    const layout = computeCanvasLayout(manifest);
    groupsEl.style.width = layout.width ? `${layout.width}px` : "";
    groupsEl.style.height = layout.height ? `${layout.height}px` : "";

    const railsLayer = document.createElement("div");
    railsLayer.className = "canvas-rails";
    const labelsLayer = document.createElement("div");
    labelsLayer.className = "canvas-column-layer";

    layout.columns.forEach((col) => {
      const rail = document.createElement("div");
      rail.className = "canvas-rail";
      rail.style.transform = `translateX(${col.x + col.width / 2}px)`;
      rail.style.height = `${layout.height}px`;
      railsLayer.appendChild(rail);

      const label = document.createElement("div");
      label.className = "canvas-column-label";
      label.style.transform = `translate(${col.x}px, 10px)`;
      label.style.width = `${col.width}px`;
      label.textContent = CANVAS_KIND_LABELS[col.kind] || col.kind;
      labelsLayer.appendChild(label);
    });

    function showDetails(node) {
      selectedId = node.id;
      const outgoing = (manifest.edges || []).filter((e) => e.from === node.id);
      const lines = [];
      lines.push(`name: ${node.name}`);
      lines.push(`kind: ${node.kind}`);
      if (node.route) lines.push(`route: ${node.route}`);
      if (node.entry_page) lines.push(`entry_page: ${node.entry_page}`);
      if (node.model) lines.push(`model: ${node.model}`);
      if (node.memory_type) lines.push(`memory_type: ${node.memory_type}`);
      if (outgoing.length) {
        lines.push("edges:");
        outgoing.forEach((edge) => {
          lines.push(`  -> ${edge.to} (${edge.kind})`);
        });
      }
      detailsEl.innerHTML = "";
      const pre = document.createElement("pre");
      pre.textContent = lines.join("\n");
      detailsEl.appendChild(pre);
      if (node.kind === "flow") {
        const runAction = document.createElement("div");
        runAction.className = "canvas-run-action";
        const btn = document.createElement("button");
        btn.className = "reload";
        btn.textContent = "Run this flow";
        btn.addEventListener("click", () => prefillRunnerWithFlow(node.name, true));
        runAction.appendChild(btn);
        detailsEl.appendChild(runAction);
      }
      document.querySelectorAll(".canvas-node").forEach((el) => el.classList.toggle(selectedCls, el.dataset.id === node.id));
      if (canvasViewport) {
        const el = document.querySelector(`.canvas-node[data-id="${node.id}"]`);
        if (el) {
          focusCanvasOnNode(el);
        }
      }
      // Best-effort log note
      fetch("/api/studio/log-note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event: "canvas_node_clicked", details: { id: node.id, kind: node.kind, name: node.name } }),
      }).catch(() => {});
      // Load inspector panel too.
      loadInspector(node.kind, node.name);
      if (node.kind === "flow") {
        prefillRunnerWithFlow(node.name, false);
      }
      if (node.kind === "rag") {
        openRagPipeline(node.name, true);
      }
    }

    const frag = document.createDocumentFragment();
    frag.appendChild(railsLayer);
    frag.appendChild(labelsLayer);

    layout.nodes.forEach((node) => {
      const shell = document.createElement("div");
      shell.className = "canvas-node-shell";
      shell.style.transform = `translate(${node.x}px, ${node.y}px)`;
      shell.style.width = `${node.width}px`;
      shell.style.height = `${node.height}px`;
      const nodeEl = document.createElement("div");
      nodeEl.className = "canvas-node";
      nodeEl.dataset.id = node.id;
      nodeEl.title = `${node.kind}: ${node.name}`;
      nodeEl.innerHTML = `<div class="canvas-node-title">${escapeHtml(node.name)}</div><div class="canvas-node-kind">${escapeHtml(CANVAS_KIND_LABELS[node.kind] || node.kind)}</div>`;
      nodeEl.addEventListener("click", () => showDetails(node));
      shell.appendChild(nodeEl);
      frag.appendChild(shell);
    });

    groupsEl.appendChild(frag);

    applyCanvasTransform();

    if (!manifest.nodes || !manifest.nodes.length) {
      detailsEl.textContent = manifest.status === "error" ? `Canvas unavailable: ${manifest.error || "unknown error"}` : "No entities found.";
    } else {
      detailsEl.textContent = "Select a node to view details.";
    }
  }

  async function loadCanvas() {
    const detailsEl = document.getElementById("canvas-details");
    if (detailsEl) detailsEl.textContent = "Loading canvas…";
    try {
      const data = await jsonRequest("/api/studio/canvas");
      renderCanvas(data);
      populateInspectorEntities(data);
      setStatus("Canvas loaded.");
    } catch (err) {
      if (detailsEl) detailsEl.textContent = `Canvas failed: ${err.message}`;
      setStatus("Canvas failed to load.", true);
    }
  }

  function renderInspector(data) {
    const container = document.getElementById("inspector-content");
    if (!container) return;
    if (!data || data.error) {
      container.textContent = data && data.error ? data.error : "Inspector unavailable.";
      return;
    }
    const relevantWarnings = warningsCache.filter((w) => (w.entity_kind || "").toLowerCase() === (data.kind || "").toLowerCase() && (w.entity_name || "") === (data.name || ""));
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
        row.innerHTML = `<div class="warning-msg">${escapeHtml(w.message || "")}</div><div class="warning-meta">${escapeHtml(w.code || "")}</div>`;
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
          prefillAsk(
            `Explain and suggest a fix for warning ${w.code}: ${w.message} (${w.entity_kind} "${w.entity_name}")`,
            { kind: w.entity_kind, name: w.entity_name, warning: w },
            true,
            mode
          );
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
      btn.addEventListener("click", () => prefillMemory(data.name, null, true));
      actions.appendChild(btn);
      container.appendChild(document.createElement("br"));
      container.appendChild(actions);
    }
    if (data.kind === "rag") {
      const btn = document.createElement("button");
      btn.className = "reload";
      btn.textContent = "View RAG pipeline";
      btn.addEventListener("click", () => openRagPipeline(data.name || "", true));
      container.appendChild(document.createElement("br"));
      container.appendChild(btn);
    }
    if (data.kind === "ai" && data.rag_pipeline) {
      const ragBtn = document.createElement("button");
      ragBtn.className = "reload";
      ragBtn.textContent = "View RAG pipeline";
      ragBtn.addEventListener("click", () => openRagPipeline(data.rag_pipeline, true));
      container.appendChild(document.createElement("br"));
      container.appendChild(ragBtn);
    }
  }

  function prefillRunnerWithFlow(flowName, activate = false) {
    if (!flowName) return;
    pendingRunnerFlow = flowName;
    if (activate) {
      activatePanel("run");
    }
    const select = document.getElementById("flow-runner-name");
    if (select && select.options.length) {
      select.value = flowName;
    }
    setStatus(`Flow "${flowName}" ready to run.`, false);
  }

  function prefillMemory(aiId, sessionId = null, activate = false) {
    if (!aiId) return;
    pendingMemoryAi = aiId;
    pendingMemorySession = sessionId;
    if (activate) {
      activatePanel("memory");
    }
    const select = document.getElementById("memory-ai-select");
    if (select && select.options.length) {
      select.value = aiId;
      loadMemoryDetails(aiId);
    }
  }

  function prefillAsk(question, ctx = null, activate = false, mode = null) {
    const qEl = document.getElementById("ask-question");
    if (qEl && question) {
      qEl.value = question;
    }
    pendingAskContext = ctx;
    if (mode) {
      setAskMode(mode);
    }
    if (activate) {
      activatePanel("ask");
      renderAskContext();
    }
  }

  function renderMemoryPlan(plan) {
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
          `<tr><td>${escapeHtml(k.kind)}</td><td>${k.enabled ? "enabled" : "disabled"}</td><td>${k.scope || ""}</td><td>${k.store || ""}</td><td>${k.window || k.retention_days || ""}</td><td>${k.pii_policy || ""}</td></tr>`
      )
      .join("");
    const recallRows = (plan.recall || [])
      .map(
        (r) =>
          `<tr><td>${escapeHtml(r.source || "")}</td><td>${r.count || ""}</td><td>${r.top_k || ""}</td><td>${r.include === false ? "skip" : "include"}</td></tr>`
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
    const container = document.getElementById("memory-sessions");
    if (!container) return;
    if (!sessions || !sessions.length) {
      container.textContent = "No sessions found yet for this AI. Run a flow to create one.";
      return;
    }
    const items = sessions
      .map(
        (s) =>
          `<li data-session="${escapeHtml(s.id || s.session_id || "")}"><strong>${escapeHtml(
            s.id || s.session_id || "(unknown)"
          )}</strong><br><small>turns: ${s.turns ?? "-"}${s.user_id ? ` • user: ${escapeHtml(s.user_id)}` : ""}</small></li>`
      )
      .join("");
    container.innerHTML = `<div class="memory-context-section"><h4>Sessions</h4><ul class="memory-sessions-list">${items}</ul></div>`;
    container.querySelectorAll("li[data-session]").forEach((el) => {
      el.addEventListener("click", () => {
        container.querySelectorAll("li").forEach((li) => li.classList.remove("active"));
        el.classList.add("active");
        loadMemoryState(aiId, el.dataset.session);
      });
      if (pendingMemorySession && (el.dataset.session === pendingMemorySession)) {
        el.click();
        pendingMemorySession = null;
      }
    });
  }

  function renderTurns(turns) {
    if (!turns || !turns.length) return "<div>No short-term history.</div>";
    return turns
      .map((t) => {
        const role = (t.role || "assistant").toLowerCase();
        return `<div class="memory-message ${role}"><strong>${escapeHtml(role)}</strong>: ${escapeHtml(t.content || "")}</div>`;
      })
      .join("");
  }

  function renderItems(items) {
    if (!items || !items.length) return "<div>No entries.</div>";
    return items
      .map((item) => {
        if (typeof item === "string") {
          return `<div class="memory-message">${escapeHtml(item)}</div>`;
        }
        return `<div class="memory-message"><strong>${escapeHtml(item.kind || item.source || "")}</strong>: ${escapeHtml(item.content || item.text || JSON.stringify(item))}</div>`;
      })
      .join("");
  }

  function renderRecallSnapshot(snapshot) {
    if (!snapshot) return "<div>No recall snapshot.</div>";
    const msgs = (snapshot.messages || []).map((m) => `<div class="memory-message ${escapeHtml(m.role || "")}"><strong>${escapeHtml(m.role || "")}</strong>: ${escapeHtml(m.content || "")}</div>`).join("");
    const diags = (snapshot.diagnostics || []).map((d) => `<div>${escapeHtml(d.source || "")} → selected ${d.selected_count || d.count || 0}</div>`).join("");
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
      <div class="memory-context-section"><h4>Session</h4><div>session: ${escapeHtml(payload.session_id || "")}${payload.user_id ? ` • user: ${escapeHtml(payload.user_id)}` : ""}</div></div>
      <div class="memory-context-section"><h4>Short-term</h4>${shortHtml}</div>
      <div class="memory-context-section"><h4>Long-term</h4>${longHtml}</div>
      <div class="memory-context-section"><h4>Profile</h4>${profileHtml}</div>
      <div class="memory-context-section"><h4>Episodic</h4>${episodicHtml}</div>
      <div class="memory-context-section"><h4>Semantic</h4>${semanticHtml}</div>
      ${recallHtml}
      <div class="memory-context-section memory-actions">
        <button class="reload ask-link" data-ai="${escapeHtml(payload.ai || "")}" data-session="${escapeHtml(payload.session_id || "")}">Ask Studio about this memory</button>
        <button class="reload ai-call-link" data-ai="${escapeHtml(payload.ai || "")}" data-session="${escapeHtml(payload.session_id || "")}">View AI call context</button>
      </div>
    `;
    container.querySelectorAll(".ask-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        const aiId = btn.dataset.ai || "";
        const sessionId = btn.dataset.session || "";
        prefillAsk(`Help me understand memory state for ${aiId}.`, { kind: "ai", ai_id: aiId, session_id: sessionId }, true);
      });
    });
    container.querySelectorAll(".ai-call-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        const aiId = btn.dataset.ai || "";
        const sessionId = btn.dataset.session || "";
        openAiCallVisualizer(aiId, sessionId, true);
      });
    });
  }

  function renderAiCall(payload) {
    const metaEl = document.getElementById("ai-call-meta");
    const sectionsEl = document.getElementById("ai-call-sections");
    if (!metaEl || !sectionsEl) return;
    if (!payload) {
      metaEl.textContent = "No AI call data.";
      sectionsEl.innerHTML = "";
      return;
    }
    metaEl.innerHTML = `<strong>${escapeHtml(payload.ai_id || "")}</strong> • model ${escapeHtml(payload.model || "")} • session ${escapeHtml(payload.session_id || "")}${payload.timestamp ? ` • ${escapeHtml(payload.timestamp)}` : ""}`;
    const messages = (payload.messages || []).map(
      (m) =>
        `<div class="ai-call-message"><div class="role">${escapeHtml(m.role || "")}${m.kind ? ` • ${escapeHtml(m.kind)}` : ""}</div><div>${escapeHtml(m.content || "")}</div></div>`
    ).join("");
    const ragMatches = (payload.rag?.matches || [])
      .map((m) => `<div class="ai-call-message"><div class="role">RAG</div><div>${escapeHtml(m.text || "")}<br><small>${escapeHtml(m.source || "")} • score ${m.score ?? ""}</small></div></div>`)
      .join("");
    const diagnosticsRows = (payload.recall_diagnostics || [])
      .map((d) => `<tr><td>${escapeHtml(d.source || "")}</td><td>${escapeHtml(d.scope || "")}</td><td>${escapeHtml(String(d.selected_count ?? d.count ?? ""))}</td><td>${escapeHtml(String(d.limit ?? ""))}</td></tr>`)
      .join("");
    const ragLink = payload.rag_pipeline ? `<button class="reload" onclick="return false;" id="ai-rag-link">View RAG pipeline</button>` : "";

    sectionsEl.innerHTML = `
      <div class="ai-call-card">
        <h4>Messages</h4>
        ${messages || "<div>No messages recorded.</div>"}
      </div>
      <div class="ai-call-card">
        <h4>Memory Snapshot</h4>
        <div>${escapeHtml(JSON.stringify(payload.memory || {}, null, 2))}</div>
      </div>
      <div class="ai-call-card">
        <h4>RAG / Vector Context</h4>
        ${ragMatches || "<div>No vector context.</div>"}
        ${ragLink}
      </div>
      <div class="ai-call-card">
        <h4>Recall diagnostics</h4>
        <table class="ai-call-table">
          <thead><tr><th>Source</th><th>Scope</th><th>Selected</th><th>Limit</th></tr></thead>
          <tbody>${diagnosticsRows || "<tr><td colspan='4'>No diagnostics.</td></tr>"}</tbody>
        </table>
      </div>
    `;
    if (payload.rag_pipeline) {
      const btn = document.getElementById("ai-rag-link");
      if (btn) {
        btn.addEventListener("click", () => openRagPipeline(payload.rag_pipeline, true));
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
      const data = await jsonRequest(`/api/studio/ai-call?ai=${encodeURIComponent(aiId)}&session=${encodeURIComponent(sessionId)}`);
      renderAiCall(data);
      pendingAiCall = null;
      setStatus("AI call loaded.");
    } catch (err) {
      if (metaEl) metaEl.textContent = `Unable to load AI call: ${err.message}`;
      setStatus("AI call load failed.", true);
    }
  }

  function openAiCallVisualizer(aiId, sessionId, focusPanel = false) {
    pendingAiCall = { ai: aiId, session: sessionId };
    if (focusPanel) {
      activatePanel("ai-call");
    }
    if (document.getElementById("panel-ai-call")?.classList.contains("active")) {
      loadAiCall(aiId, sessionId);
    }
  }

  function openRagPipeline(name, focusPanel = false) {
    if (!name) return;
    if (focusPanel) activatePanel("rag");
    loadRagPipeline(name);
    const list = document.getElementById("rag-pipelines-list");
    if (list) {
      list.querySelectorAll("li").forEach((li) => li.classList.toggle("active", li.dataset.name === name));
    }
  }

  function addRunToHistory(result) {
    const entry = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      flow: result.flow || "",
      timestamp: new Date().toISOString(),
      result,
    };
    flowRunHistory.unshift(entry);
    while (flowRunHistory.length > 5) flowRunHistory.pop();
    renderRunHistory();
  }

  function renderRunHistory() {
    const sel = document.getElementById("flow-run-history");
    if (!sel) return;
    if (!flowRunHistory.length) {
      sel.innerHTML = '<option value="">No recent runs</option>';
      return;
    }
    sel.innerHTML = flowRunHistory
      .map((entry, idx) => `<option value="${entry.id}">${idx === 0 ? "Latest" : `Run ${idx + 1}`} — ${escapeHtml(entry.flow)} @ ${escapeHtml(formatTimestamp(entry.timestamp))}</option>`)
      .join("");
  }

  function selectHistoryRun(id) {
    const entry = flowRunHistory.find((e) => e.id === id);
    if (!entry) return;
    renderFlowRunResult(entry.result);
  }

  async function loadMemoryDetails(aiId) {
    if (!aiId) return;
    try {
      const [plan, sessions] = await Promise.all([
        jsonRequest(`/api/memory/ai/${encodeURIComponent(aiId)}/plan`),
        jsonRequest(`/api/memory/ai/${encodeURIComponent(aiId)}/sessions`),
      ]);
      renderMemoryPlan(plan);
      renderMemorySessions(aiId, sessions.sessions || sessions.session || sessions || []);
    } catch (err) {
      renderJsonIn("memory-plan", `Error loading memory: ${err.message}`);
      renderJsonIn("memory-sessions", "Unable to load sessions.");
      setStatus("Error loading memory.", true);
    }
  }

  async function loadMemoryState(aiId, sessionId) {
    if (!aiId || !sessionId) {
      renderMemoryState(null);
      return;
    }
    try {
      const payload = await jsonRequest(`/api/memory/ai/${encodeURIComponent(aiId)}/state?session_id=${encodeURIComponent(sessionId)}`);
      renderMemoryState(payload);
      setStatus("Memory state loaded.");
    } catch (err) {
      renderJsonIn("memory-state", `Error loading memory state: ${err.message}`);
      setStatus("Error loading memory state.", true);
    }
  }

  async function loadMemoryAIs() {
    const select = document.getElementById("memory-ai-select");
    const planContainer = document.getElementById("memory-plan");
    if (!select) return;
    select.innerHTML = '<option value="">Loading…</option>';
    try {
      const data = await jsonRequest("/api/memory/ais");
      const ais = data.ais || [];
      if (!ais.length) {
        select.innerHTML = '<option value="">No AIs with memory</option>';
        if (planContainer) planContainer.textContent = "No AIs with memory configured in this program.";
        return;
      }
      select.innerHTML = ais.map((a) => `<option value="${escapeHtml(a.id)}">${escapeHtml(a.name || a.id)}</option>`).join("");
      const desired = (pendingMemoryAi && ais.some((a) => a.id === pendingMemoryAi)) ? pendingMemoryAi : select.value;
      if (desired) {
        select.value = desired;
        pendingMemoryAi = null;
        await loadMemoryDetails(desired);
        if (pendingMemorySession) {
          await loadMemoryState(desired, pendingMemorySession);
          pendingMemorySession = null;
        }
      }
    } catch (err) {
      if (planContainer) planContainer.textContent = `Error loading AIs: ${err.message}`;
      setStatus("Error loading memory AIs.", true);
    }
  }

  function renderAskContext() {
    const ctxEl = document.getElementById("ask-context");
    if (!ctxEl) return;
    if (!pendingAskContext) {
      ctxEl.textContent = "No extra context set.";
      return;
    }
    ctxEl.textContent = `Context: ${JSON.stringify(pendingAskContext, null, 2)}`;
  }

  async function runAskStudio() {
    const qEl = document.getElementById("ask-question");
    const ansEl = document.getElementById("ask-answer");
    const snEl = document.getElementById("ask-snippets");
    if (!qEl) return;
    const question = qEl.value.trim();
    if (!question) {
      if (ansEl) ansEl.textContent = "Enter a question first.";
      return;
    }
    if (ansEl) ansEl.textContent = "Asking Studio…";
    if (snEl) snEl.innerHTML = "";
    try {
      const body = { question };
      if (pendingAskContext) body.context = pendingAskContext;
      body.mode = askMode || "explain";
      const resp = await jsonRequest("/api/studio/ask", { method: "POST", body: JSON.stringify(body) });
      if (ansEl) {
        ansEl.classList.remove("revealed");
        ansEl.textContent = resp.answer || "(no answer)";
        // force reflow for animation restart
        void ansEl.offsetWidth;
        ansEl.classList.add("revealed");
      }
      renderAskSnippets(resp.suggested_snippets || []);
      setStatus("Ask Studio answered.");
    } catch (err) {
      if (ansEl) ansEl.textContent = "Ask Studio is currently unavailable. Check provider configuration or try again later.";
      setStatus("Ask Studio failed.", true);
    }
  }

  async function loadStudioFlows() {
    const select = document.getElementById("flow-runner-name");
    const output = document.getElementById("flow-runner-output");
    if (!select) return;
    if (output) output.textContent = "Loading flows…";
    try {
      const data = await jsonRequest("/api/studio/flows");
      const flows = data.flows || [];
      if (!flows.length) {
        select.innerHTML = '<option value="">No flows found</option>';
        if (output) output.textContent = "No flows found in the current program.";
        return;
      }
      select.innerHTML = flows
        .map((f) => `<option value="${escapeHtml(f.name)}">${escapeHtml(f.name)}${f.steps ? ` (${f.steps} steps)` : ""}</option>`)
        .join("");
      if (pendingRunnerFlow && flows.some((f) => f.name === pendingRunnerFlow)) {
        select.value = pendingRunnerFlow;
        pendingRunnerFlow = null;
      }
      if (output) output.textContent = "Select a flow to run.";
    } catch (err) {
      if (output) output.textContent = `Could not load flows: ${err.message}`;
      setStatus("Error loading flows.", true);
    }
  }

  function renderFlowRunResult(result) {
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

    let html = `<div class="flow-run-summary ${hasErrors ? "error" : "ok"}">Flow "${escapeHtml(result.flow || "")}" ${hasErrors ? "finished with errors" : "completed"}</div>`;
    html += `<div class="flow-run-summary">Run at ${escapeHtml(formatTimestamp(new Date().toISOString()))}${result.session_id ? ` • Session ${escapeHtml(result.session_id)}` : ""}</div>`;
    if (result.errors && result.errors.length) {
      html += `<div class="flow-run-errors">${result.errors.map((e) => `<div>${escapeHtml(e)}</div>`).join("")}</div>`;
    }
    if (steps.length) {
      html += '<div class="timeline">';
      steps.forEach((step) => {
        const statusCls = step.success === false ? "error" : "success";
        const target = step.target ? ` → ${escapeHtml(step.target)}` : "";
        const duration = formatDurationSeconds(step.duration_seconds);
        const preview = step.output_preview ? `<div class="preview">${escapeHtml(step.output_preview)}</div>` : "";
        const err = step.error ? `<div class="preview">Error: ${escapeHtml(step.error)}</div>` : "";
        const aiId = step.ai_id || (step.kind === "ai" ? step.target : "");
        const memoryLink = step.memory_kinds_used && step.memory_kinds_used.length
          ? `<button class="reload memory-link" data-ai="${escapeHtml(aiId || "")}" data-session="${escapeHtml(result.session_id || "")}">View memory</button>`
          : "";
        const aiCallLink = aiId
          ? `<button class="reload ai-call-link" data-ai="${escapeHtml(aiId)}" data-session="${escapeHtml(result.session_id || "")}">View AI context</button>`
          : "";
        const askLink = step.error
          ? `<button class="reload ask-link" data-mode="generate_flow" data-question="${escapeHtml(`Improve or fix step ${step.name}: ${step.error}`)}" data-flow="${escapeHtml(result.flow || "")}">Ask Studio</button>`
          : "";
        const ragInfo = step.rag_pipeline ? `<span>RAG: ${escapeHtml(step.rag_pipeline)}</span>` : "";
        const toolInfo = step.tool_method || step.tool_url ? `<span>Tool: ${escapeHtml(step.tool_method || "")} ${escapeHtml(step.tool_url || "")}</span>` : "";
        const slowCls = step.duration_seconds && step.duration_seconds >= slowThreshold ? "slow" : "";
        html += `<div class="timeline-step ${statusCls} ${slowCls}">
          <div class="dot"></div>
          <div class="timeline-card">
            <div class="timeline-head">
              <span>[${(step.index ?? steps.indexOf(step))}] ${escapeHtml(step.kind || "step")} ${escapeHtml(step.name || "")}${target}</span>
              <span class="badge ${statusCls}">${statusCls === "error" ? "Error" : "Success"}</span>
            </div>
            <div class="timeline-meta">
              ${duration ? `<span>Duration ${duration}</span>` : ""}
              ${step.cost ? `<span>Cost ${escapeHtml(String(step.cost))}</span>` : ""}
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
    const finalState = result.final_state && Object.keys(result.final_state).length ? `<details class="flow-final-state"><summary>Final state</summary><pre>${escapeHtml(JSON.stringify(result.final_state, null, 2))}</pre></details>` : "";
    container.innerHTML = html + finalState;
    container.querySelectorAll(".memory-link").forEach((btn) => {
      btn.addEventListener("click", () => prefillMemory(btn.dataset.ai, btn.dataset.session || null, true));
    });
    container.querySelectorAll(".ai-call-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        const aiId = btn.dataset.ai || "";
        const sessionId = btn.dataset.session || "";
        openAiCallVisualizer(aiId, sessionId, true);
      });
    });
    container.querySelectorAll(".ask-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        const question = btn.dataset.question || "Explain this error.";
        prefillAsk(question, { kind: "flow", name: result.flow, flow_run: result }, true, btn.dataset.mode || null);
      });
    });
  }

  async function runStudioFlow() {
    const select = document.getElementById("flow-runner-name");
    const input = document.getElementById("flow-runner-input");
    const flowName = select ? select.value.trim() : "";
    if (!flowName) {
        renderFlowRunResult({ flow: "", success: false, errors: ["Select a flow to run."], steps: [] });
        setStatus("Flow name is required.", true);
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
        setStatus("Invalid JSON payload.", true);
        return;
      }
    }
    setStatus(`Running flow "${flowName}"…`);
    try {
      const body = { flow: flowName };
      if (Object.keys(statePayload).length) body.state = statePayload;
      if (Object.keys(metadataPayload).length) body.metadata = metadataPayload;
      const data = await jsonRequest("/api/studio/run-flow", {
        method: "POST",
        body: JSON.stringify(body),
      });
      renderFlowRunResult(data);
      addRunToHistory(data);
      setStatus("Flow run complete.");
      if (data.session_id) {
        pendingMemorySession = data.session_id;
      }
      fetch("/api/studio/log-note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event: "flow_run_viewed", details: { flow: flowName, success: data.success } }),
      }).catch(() => {});
    } catch (err) {
      const fallback = { flow: flowName, success: false, errors: [err.message], steps: [] };
      renderFlowRunResult(fallback);
      addRunToHistory(fallback);
      setStatus("Error running flow.", true);
    }
  }

  async function loadInspector(kind, name) {
    if (!kind || !name) return;
    const content = document.getElementById("inspector-content");
    if (content) content.textContent = `Loading ${kind} ${name}…`;
    try {
      const data = await jsonRequest(`/api/studio/inspect?kind=${encodeURIComponent(kind)}&name=${encodeURIComponent(name)}`);
      renderInspector(data);
      if (data.kind === "flow") {
        prefillRunnerWithFlow(data.name, false);
      }
      setStatus("Inspector loaded.");
    } catch (err) {
      if (content) content.textContent = `Inspector failed: ${err.message}`;
      setStatus("Inspector failed.", true);
    }
  }

  function populateInspectorEntities(manifest) {
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
  }

  function renderBanner(message, tone = "warn") {
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

  async function loadWarnings() {
    try {
      const data = await jsonRequest("/api/studio/warnings");
      warningsCache = data.warnings || [];
      renderWarningsIndicator();
      renderWarningsPanel();
    } catch (err) {
      warningsCache = [];
      renderWarningsIndicator();
      renderWarningsPanel(`Warnings unavailable: ${err.message}`);
    }
  }

  function renderWarningsIndicator() {
    const btn = document.getElementById("warnings-toggle");
    const countEl = document.getElementById("warnings-count");
    if (!btn || !countEl) return;
    const count = warningsCache.length;
    countEl.textContent = count;
    btn.classList.toggle("has-warnings", count > 0);
  }

  function goToWarning(w) {
    const kind = (w.entity_kind || "").toLowerCase();
    const name = w.entity_name || "";
    if (!kind || !name) return;
    if (kind === "rag") {
      openRagPipeline(name, true);
      return;
    }
    const inspectorKinds = ["flow", "page", "ai", "agent", "tool", "memory", "app"];
    if (inspectorKinds.includes(kind)) {
      const kindSelect = document.getElementById("inspector-kind");
      const entitySelect = document.getElementById("inspector-entity");
      if (kindSelect) kindSelect.value = kind;
      if (entitySelect) entitySelect.value = name;
      activatePanel("inspector");
      loadInspector(kind, name);
    }
  }

  function renderWarningsPanel(errorText) {
    const panel = document.getElementById("warnings-panel");
    if (!panel) return;
    if (errorText) {
      panel.innerHTML = `<div class="warning-card"><div class="warning-main">${escapeHtml(errorText)}</div></div>`;
      return;
    }
    if (!warningsCache.length) {
      panel.innerHTML = "<div class=\"warning-card\"><div class=\"warning-main\">No warnings detected.</div></div>";
      return;
    }
    panel.innerHTML = `<div class="warning-list">
      ${warningsCache
        .map(
          (w, idx) =>
            `<div class="warning-card" data-index="${idx}">
              <div class="warning-main">
                <div class="warning-badge">${escapeHtml(w.code || "WARN")}</div>
                <div class="warning-msg">${escapeHtml(w.message || "")}</div>
                <div class="warning-meta">${escapeHtml(w.entity_kind || "")}: ${escapeHtml(w.entity_name || "")}${w.file ? " • " + escapeHtml(w.file) : ""}</div>
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
        const w = warningsCache[idx];
        if (w) {
          goToWarning(w);
        }
      });
    });
    panel.querySelectorAll(".warning-ask").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.dataset.idx || "0");
        const w = warningsCache[idx];
        if (!w) return;
        const modeMap = {
          flow: "generate_flow",
          tool: "generate_tool",
          rag: "generate_rag",
          page: "generate_page",
          agent: "generate_agent",
        };
        const mode = modeMap[(w.entity_kind || "").toLowerCase()] || "explain";
        prefillAsk(
          `Explain and suggest a fix for warning ${w.code}: ${w.message} (${w.entity_kind} "${w.entity_name}")`,
          { kind: w.entity_kind, name: w.entity_name, warning: w },
          true,
          mode
        );
      });
    });
  }

  function toggleWarningsPanel(forceShow) {
    const panel = document.getElementById("warnings-panel");
    if (!panel) return;
    const shouldShow = typeof forceShow === "boolean" ? forceShow : panel.classList.contains("hidden");
    panel.classList.toggle("hidden", !shouldShow);
    if (shouldShow && (!warningsCache || !warningsCache.length)) {
      loadWarnings();
    }
  }

  function closeCommandPalette() {
    const overlay = document.getElementById("command-palette-overlay");
    if (!overlay) return;
    overlay.classList.add("hidden");
    commandPaletteOpen = false;
    commandSelectedIndex = 0;
    const input = document.getElementById("command-input");
    if (input) input.value = "";
    renderCommandResults();
  }

  function openCommandPalette() {
    const overlay = document.getElementById("command-palette-overlay");
    const input = document.getElementById("command-input");
    if (!overlay || !input) return;
    overlay.classList.remove("hidden");
    commandPaletteOpen = true;
    ensureCommandsBuilt();
    renderCommandResults();
    requestAnimationFrame(() => input.focus());
  }

  function toggleCommandPalette() {
    if (commandPaletteOpen) {
      closeCommandPalette();
    } else {
      openCommandPalette();
    }
  }

  async function loadRagPipelinesList() {
    const listEl = document.getElementById("rag-pipelines-list");
    if (!listEl) return;
    listEl.innerHTML = "<li>Loading pipelines…</li>";
    try {
      const data = await jsonRequest("/api/studio/rag/list");
      const pipelines = data.pipelines || [];
      ragPipelineCache = pipelines;
      if (!pipelines.length) {
        listEl.innerHTML = "<li>No pipelines found.</li>";
        return;
      }
      listEl.innerHTML = pipelines
        .map((name) => `<li data-name="${escapeHtml(name)}">${escapeHtml(name)}</li>`)
        .join("");
      listEl.querySelectorAll("li").forEach((li) => {
        li.addEventListener("click", () => {
          listEl.querySelectorAll("li").forEach((n) => n.classList.remove("active"));
          li.classList.add("active");
          loadRagPipeline(li.dataset.name);
        });
      });
    } catch (err) {
      listEl.innerHTML = `<li>Error loading pipelines: ${escapeHtml(err.message)}</li>`;
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
      const data = await jsonRequest(`/api/studio/rag/pipeline?name=${encodeURIComponent(name)}`);
      renderRagPipeline(data);
    } catch (err) {
      if (titleEl) titleEl.textContent = `Unable to load pipeline: ${err.message}`;
    }
  }

  function renderRagPipeline(manifest) {
    if (!manifest) return;
    const titleEl = document.getElementById("rag-pipeline-title");
    const stagesEl = document.getElementById("rag-pipeline-stages");
    const detailsEl = document.getElementById("rag-pipeline-details");
    if (titleEl) titleEl.textContent = `Pipeline: ${manifest.name || ""}${manifest.default_vector_store ? ` • default store ${manifest.default_vector_store}` : ""}`;
    if (stagesEl) {
      const stages = manifest.stages || [];
      const parts = [];
      stages.forEach((stage, idx) => {
        parts.push(`<div class="rag-stage">
          <h5>${escapeHtml(stage.name || `Stage ${idx + 1}`)}</h5>
          <div class="meta">
            <span>kind: ${escapeHtml(stage.kind || "")}</span>
            ${stage.ai ? `<span>ai: ${escapeHtml(stage.ai)}</span>` : ""}
            ${stage.vector_store ? `<span>vector_store: ${escapeHtml(stage.vector_store)}</span>` : ""}
            ${stage.frame ? `<span>frame: ${escapeHtml(stage.frame)}</span>` : ""}
            ${stage.graph ? `<span>graph: ${escapeHtml(stage.graph)}</span>` : ""}
            ${stage.top_k ? `<span>top_k: ${escapeHtml(String(stage.top_k))}</span>` : ""}
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

  async function reparseNow() {
    setStatus("Re-parsing…");
    try {
      const resp = await jsonRequest("/api/studio/reparse", { method: "POST" });
      const errors = resp.errors || [];
      if (resp.success) {
        renderBanner(`IR rebuilt at ${resp.timestamp || ""}`, "warn");
        setStatus("Re-parse complete.");
      } else if (errors.length) {
        const first = errors[0] || {};
        const msg = `${first.file || "program"}${first.line ? ":" + first.line : ""}: ${first.message || "IR error"}`;
        renderBanner(`IR contains errors (${errors.length}). ${msg}`, "error");
        setStatus("Re-parse encountered errors.", true);
        prefillAsk(`Explain this IR error and how to fix it: ${msg}`, { kind: "error", error: first }, false);
      } else {
        renderBanner("IR re-parse failed.", "error");
        setStatus("Re-parse failed.", true);
      }
      loadStudioStatus();
      loadCanvas();
      loadStudioFlows();
      loadRagPipelinesList();
      loadWarnings();
      const inspectorPanelActive = document.getElementById("panel-inspector")?.classList.contains("active");
      if (inspectorPanelActive) {
        const kind = document.getElementById("inspector-kind")?.value;
        const name = document.getElementById("inspector-entity")?.value;
        if (kind && name) {
          loadInspector(kind, name);
        }
      }
    } catch (err) {
      renderBanner(`Re-parse failed: ${err.message}`, "error");
      setStatus("Re-parse failed.", true);
    }
  }

  function buildCommandListFromCanvas() {
    const manifest = window.n3CanvasManifest || {};
    const nodes = manifest.nodes || [];
    nodes.forEach((node) => {
      const kind = node.kind || "";
      const name = node.name || "";
      if (!name) return;
      const id = `${kind}:${name}`;
      let label = name;
      let hint = kind;
      let action = null;
      if (kind === "flow") {
        label = `Run flow: ${name}`;
        hint = "flow";
        action = () => {
          prefillRunnerWithFlow(name, true);
        };
      } else if (kind === "rag") {
        label = `View RAG pipeline: ${name}`;
        hint = "rag pipeline";
        action = () => openRagPipeline(name, true);
      } else {
        label = `Inspect ${kind}: ${name}`;
        action = () => {
          activatePanel("inspector");
          loadInspector(kind, name);
        };
      }
      commandItems.push({ id, label, hint, run: action });
    });
  }

  function buildCommandListStatic() {
    const panels = [
      { id: "panel:overview", label: "Open Overview", hint: "panel", run: () => activatePanel("overview") },
      { id: "panel:canvas", label: "Open Canvas", hint: "panel", run: () => activatePanel("canvas") },
      { id: "panel:inspector", label: "Open Inspector", hint: "panel", run: () => activatePanel("inspector") },
      { id: "panel:run", label: "Open Flow Runner", hint: "panel", run: () => activatePanel("run") },
      { id: "panel:memory", label: "Open Memory Viewer", hint: "panel", run: () => activatePanel("memory") },
      { id: "panel:rag", label: "Open RAG Pipelines", hint: "panel", run: () => activatePanel("rag") },
      { id: "panel:logs", label: "Open Logs", hint: "panel", run: () => activatePanel("logs") },
      { id: "panel:ai-call", label: "Open AI Call Visualizer", hint: "panel", run: () => activatePanel("ai-call") },
      { id: "panel:ask", label: "Open Ask Studio", hint: "panel", run: () => activatePanel("ask") },
      { id: "command:reparse", label: "Re-Parse Now", hint: "command", run: () => reparseNow() },
    ];
    commandItems.push(...panels);
  }

  function buildCommandListFlows() {
    const select = document.getElementById("flow-runner-name");
    if (!select || !select.options) return;
    Array.from(select.options)
      .map((opt) => opt.value)
      .filter(Boolean)
      .forEach((flow) => {
        commandItems.push({
          id: `flow:${flow}`,
          label: `Run flow: ${flow}`,
          hint: "flow",
          run: () => prefillRunnerWithFlow(flow, true),
        });
      });
  }

  function buildCommandListRag() {
    (ragPipelineCache || []).forEach((name) => {
      commandItems.push({
        id: `rag:${name}`,
        label: `View RAG pipeline: ${name}`,
        hint: "rag",
        run: () => openRagPipeline(name, true),
      });
    });
  }

  function ensureCommandsBuilt() {
    commandItems = [];
    buildCommandListStatic();
    buildCommandListFromCanvas();
    buildCommandListFlows();
    buildCommandListRag();
    commandFiltered = [...commandItems];
  }

  function renderCommandResults() {
    const container = document.getElementById("command-results");
    const input = document.getElementById("command-input");
    if (!container) return;
    const query = (input && input.value.trim().toLowerCase()) || "";
    if (!query) {
        commandFiltered = [...commandItems];
    } else {
        commandFiltered = commandItems.filter((cmd) => cmd.label.toLowerCase().includes(query));
    }
    if (commandSelectedIndex >= commandFiltered.length) commandSelectedIndex = 0;
    const html = commandFiltered
      .map(
        (cmd, idx) =>
          `<div class="command-item ${idx === commandSelectedIndex ? "active" : ""}" data-id="${cmd.id}">
            <span>${escapeHtml(cmd.label)}</span>
            <span class="hint">${escapeHtml(cmd.hint || "")}</span>
          </div>`
      )
      .join("");
    container.innerHTML = html || '<div class="command-item">No commands</div>';
    container.querySelectorAll(".command-item").forEach((el, idx) => {
      el.addEventListener("click", () => {
        commandSelectedIndex = idx;
        executeSelectedCommand();
      });
    });
  }

  function executeSelectedCommand() {
    const cmd = commandFiltered[commandSelectedIndex];
    if (!cmd || !cmd.run) return;
    cmd.run();
    closeCommandPalette();
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

  async function loadStudioStatus() {
    try {
      const status = await jsonRequest("/api/studio/status");
      if (status.ir_status === "error") {
        const err = status.ir_error || {};
        const loc = [err.file, err.line, err.column].filter(Boolean).join(":");
        const prefix = loc ? `${loc}: ` : "";
        const message = `Your project has errors. ${prefix}${err.message || ""}`.trim();
        renderBanner(`${message} `, "error");
        const banner = document.getElementById("status-banner");
        if (banner) {
          const btn = document.createElement("button");
          btn.className = "reload";
          btn.textContent = "Ask Studio about this error";
          btn.addEventListener("click", () => {
            prefillAsk(`${message} How do I fix this?`, { kind: "error", error: err }, true);
          });
          banner.appendChild(document.createTextNode(" "));
          banner.appendChild(btn);
        }
        setStatus("Your project has errors.", true);
        return;
      }
      const aiFiles = status.ai_files || 0;
      const aiPaths = status.ai_file_paths || [];
      if (aiFiles === 0) {
        renderBanner("No .ai files found. Add one to get started.", "warn");
      } else if (aiFiles === 1 && aiPaths.length === 1 && ["starter.ai", "app.ai", "main.ai"].includes(aiPaths[0])) {
        renderBanner("Starter project created. Edit starter.ai to begin.", "warn");
      } else if (status.watcher_supported === false) {
        renderBanner("File system watcher unavailable; changes will not auto-reload.", "warn");
      } else if (status.watcher_active === false) {
        renderBanner("File system watcher inactive; changes will not auto-reload.", "warn");
      } else if (status.studio_static_available === false) {
        renderBanner("Packaged Studio assets not found. Reinstall or rebuild (development only).", "warn");
      } else {
        renderBanner("");
      }
    } catch (err) {
      renderBanner(`Could not check project status: ${err.message}`, "warn");
      setStatus("Status check failed.", true);
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
        case "run":
          loadStudioFlows();
          break;
        case "traces":
          loadTraces();
          break;
        case "memory":
          loadMemory();
          break;
        case "ask":
          renderAskContext();
          break;
        case "ai-call":
          if (pendingAiCall) {
            loadAiCall(pendingAiCall.ai, pendingAiCall.session);
          }
          break;
        case "rag":
          loadRagPipelinesList();
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
    loadMemoryAIs();
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
      "memory-refresh": loadMemory,
      "rag-run": runRagQuery,
      "rag-load": loadRagPipelinesList,
      "diagnostics-run": runDiagnostics,
      "run-app": runApp,
      "run-flow": runFlow,
      "flow-runner-refresh": loadStudioFlows,
      "flow-runner-run": runStudioFlow,
      "ask-run": runAskStudio,
      "logs-clear": () => renderLogs([]),
      "canvas-reload": loadCanvas,
      "inspector-load": () => {
        const kind = document.getElementById("inspector-kind")?.value;
        const name = document.getElementById("inspector-entity")?.value;
        loadInspector(kind, name);
      },
      "reparse-now": reparseNow,
    };
    document.querySelectorAll("button.reload").forEach((btn) => {
      const action = btn.dataset.action;
      if (actions[action]) {
        btn.addEventListener("click", actions[action]);
      }
    });

    const kindSelect = document.getElementById("inspector-kind");
    if (kindSelect) {
      kindSelect.addEventListener("change", () => {
        populateInspectorEntities(window.n3CanvasManifest || {});
      });
    }
    const memorySelect = document.getElementById("memory-ai-select");
    if (memorySelect) {
      memorySelect.addEventListener("change", () => loadMemoryDetails(memorySelect.value));
    }

    document.querySelectorAll(".theme-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const theme = btn.dataset.theme || "light";
        setTheme(theme);
      });
    });

    const historySelect = document.getElementById("flow-run-history");
    if (historySelect) {
      historySelect.addEventListener("change", () => {
        if (historySelect.value) {
          selectHistoryRun(historySelect.value);
        }
      });
    }

    const presentationBtn = document.getElementById("presentation-toggle");
    if (presentationBtn) {
      presentationBtn.addEventListener("click", togglePresentationMode);
    }

    document.querySelectorAll(".ask-mode-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        setAskMode(btn.dataset.mode || "explain");
      });
    });

    const warningsBtn = document.getElementById("warnings-toggle");
    if (warningsBtn) {
      warningsBtn.addEventListener("click", () => toggleWarningsPanel());
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initButtons();
    activatePanel("overview");
    loadProviderStatus();
    loadStudioStatus();
    connectLogsStream();
    loadCanvas();
    renderRunHistory();
    setStatus("Ready.");
  });

  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      toggleCommandPalette();
    }
    if (!commandPaletteOpen && event.shiftKey && event.key.toLowerCase() === "p") {
      const tag = (document.activeElement && document.activeElement.tagName) || "";
      if (!["INPUT", "TEXTAREA"].includes(tag)) {
        event.preventDefault();
        togglePresentationMode();
        return;
      }
    }
    if (!commandPaletteOpen) return;
    if (event.key === "Escape") {
      closeCommandPalette();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      commandSelectedIndex = Math.min(commandSelectedIndex + 1, (commandFiltered.length || 1) - 1);
      renderCommandResults();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      commandSelectedIndex = Math.max(commandSelectedIndex - 1, 0);
      renderCommandResults();
    } else if (event.key === "Enter") {
      event.preventDefault();
      executeSelectedCommand();
    }
  });

  const commandOverlay = document.getElementById("command-palette-overlay");
  if (commandOverlay) {
    commandOverlay.addEventListener("click", (event) => {
      if (event.target === commandOverlay) {
        closeCommandPalette();
      }
    });
  }

  const commandInput = document.getElementById("command-input");
  if (commandInput) {
    commandInput.addEventListener("input", () => {
      commandSelectedIndex = 0;
      renderCommandResults();
    });
  }

  function setTheme(theme) {
    currentTheme = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = currentTheme;
    try {
      localStorage.setItem("n3_studio_theme", currentTheme);
    } catch (err) {
      // ignore storage errors
    }
    document.querySelectorAll(".theme-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.theme === currentTheme);
    });
  }

  function initTheme() {
    try {
      const stored = localStorage.getItem("n3_studio_theme");
      if (stored) {
        setTheme(stored);
        return;
      }
    } catch (err) {
      // ignore
    }
    setTheme("light");
  }

  function setAskMode(mode) {
    askMode = mode || "explain";
    document.querySelectorAll(".ask-mode-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mode === askMode);
    });
    try {
      localStorage.setItem("n3_studio_ask_mode", askMode);
    } catch (err) {
      // ignore storage errors
    }
    const hint = document.getElementById("ask-mode-hint");
    if (hint) {
      const messages = {
        explain: "Ask Studio to explain, debug, or summarize.",
        generate_flow: "Ask Studio to generate a flow snippet.",
        generate_page: "Ask Studio to generate a page/UI snippet.",
        generate_tool: "Ask Studio to generate a tool definition.",
        generate_agent: "Ask Studio to generate an agent configuration.",
        generate_rag: "Ask Studio to generate a RAG pipeline.",
      };
      hint.textContent = messages[askMode] || messages.explain;
    }
  }

  function initAskMode() {
    try {
      const stored = localStorage.getItem("n3_studio_ask_mode");
      if (stored) {
        setAskMode(stored);
        return;
      }
    } catch (err) {
      // ignore
    }
    setAskMode("explain");
  }

  function renderAskSnippets(snippets) {
    const snEl = document.getElementById("ask-snippets");
    if (!snEl) return;
    if (!snippets || !snippets.length) {
      snEl.innerHTML = "";
      return;
    }
    snEl.innerHTML = snippets
      .map(
        (s, idx) =>
          `<div class="snippet" data-index="${idx}">
            <div class="snippet-kind">${escapeHtml((s.kind || "snippet").toUpperCase())}</div>
            <div class="snippet-title">${escapeHtml(s.title || "Suggested snippet")}</div>
            <button class="snippet-copy" data-dsl-index="${idx}">Copy</button>
            <code>${escapeHtml(s.dsl || "")}</code>
            ${s.notes ? `<div class="snippet-notes">${escapeHtml(s.notes || "")}</div>` : ""}
          </div>`
      )
      .join("");
    snEl.querySelectorAll(".snippet-copy").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const idx = Number(btn.dataset.dslIndex || "0");
        const snippet = snippets[idx];
        if (!snippet || !snippet.dsl) return;
        try {
          await navigator.clipboard.writeText(snippet.dsl);
          btn.textContent = "Copied";
          setTimeout(() => {
            btn.textContent = "Copy";
          }, 1200);
        } catch (err) {
          btn.textContent = "Copy failed";
          setTimeout(() => {
            btn.textContent = "Copy";
          }, 1200);
        }
      });
    });
  }

  function setPresentationMode(enabled) {
    presentationMode = Boolean(enabled);
    document.documentElement.dataset.presentation = presentationMode ? "true" : "false";
    try {
      localStorage.setItem("n3_studio_presentation_mode", presentationMode ? "true" : "false");
    } catch (err) {
      // ignore
    }
    const btn = document.getElementById("presentation-toggle");
    if (btn) {
      btn.classList.toggle("active", presentationMode);
      btn.setAttribute("aria-pressed", presentationMode ? "true" : "false");
      btn.textContent = presentationMode ? "Presentation On" : "Presentation";
    }
    if (window.n3CanvasManifest) {
      renderCanvas(window.n3CanvasManifest);
    }
  }

  function togglePresentationMode() {
    setPresentationMode(!presentationMode);
  }

  function initPresentationMode() {
    try {
      const stored = localStorage.getItem("n3_studio_presentation_mode");
      if (stored === "true") {
        setPresentationMode(true);
        return;
      }
    } catch (err) {
      // ignore
    }
    setPresentationMode(false);
  }

  initTheme();
  initAskMode();
  initPresentationMode();
  loadWarnings();
})();
