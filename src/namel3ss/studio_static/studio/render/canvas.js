(function (N) {
  const render = (N.render = N.render || {});
  const canvas = (render.canvas = render.canvas || {});
  const state = N.state || {};
  const layout = (N.render && N.render.layout) || {};

  canvas.applyCanvasTransform = function applyCanvasTransform() {
    if (!state.canvasGroupsEl) return;
    state.canvasGroupsEl.style.transform = `translate(${state.canvasOffset.x}px, ${state.canvasOffset.y}px) scale(${state.canvasScale})`;
  };

  canvas.handleCanvasWheel = function handleCanvasWheel(event) {
    if (!state.canvasViewport || !state.canvasGroupsEl) return;
    event.preventDefault();
    const rect = state.canvasViewport.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const prevScale = state.canvasScale;
    const scaleDelta = Math.exp(-event.deltaY * 0.0012);
    state.canvasScale = N.utils.clamp(state.canvasScale * scaleDelta, 0.6, 1.8);
    const factor = state.canvasScale / prevScale;
    state.canvasOffset.x = px - (px - state.canvasOffset.x) * factor;
    state.canvasOffset.y = py - (py - state.canvasOffset.y) * factor;
    canvas.applyCanvasTransform();
  };

  canvas.handleCanvasMouseDown = function handleCanvasMouseDown(event) {
    if (!state.canvasViewport) return;
    state.isCanvasPanning = true;
    state.canvasPanStart = { x: event.clientX - state.canvasOffset.x, y: event.clientY - state.canvasOffset.y };
    state.canvasViewport.style.cursor = "grabbing";
  };

  canvas.handleCanvasMouseMove = function handleCanvasMouseMove(event) {
    if (!state.isCanvasPanning) return;
    state.canvasOffset.x = event.clientX - state.canvasPanStart.x;
    state.canvasOffset.y = event.clientY - state.canvasPanStart.y;
    canvas.applyCanvasTransform();
  };

  canvas.handleCanvasMouseUp = function handleCanvasMouseUp() {
    if (!state.canvasViewport) return;
    state.isCanvasPanning = false;
    state.canvasViewport.style.cursor = "grab";
  };

  canvas.focusCanvasOnNode = function focusCanvasOnNode(nodeEl) {
    if (!state.canvasViewport || !nodeEl) return;
    const viewportRect = state.canvasViewport.getBoundingClientRect();
    const nodeRect = nodeEl.getBoundingClientRect();
    const targetX = viewportRect.left + viewportRect.width / 2 - (nodeRect.left + nodeRect.width / 2);
    const targetY = viewportRect.top + viewportRect.height / 2 - (nodeRect.top + nodeRect.height / 2);
    state.canvasOffset.x += targetX;
    state.canvasOffset.y += targetY;
    canvas.applyCanvasTransform();
  };

  canvas.initCanvasInteractions = function initCanvasInteractions() {
    if (state.canvasViewport && state.canvasGroupsEl) return;
    state.canvasViewport = document.getElementById("canvas-viewport");
    state.canvasGroupsEl = document.getElementById("canvas-groups");
    if (!state.canvasViewport || !state.canvasGroupsEl) return;
    state.canvasViewport.addEventListener("wheel", canvas.handleCanvasWheel, { passive: false });
    state.canvasViewport.addEventListener("mousedown", canvas.handleCanvasMouseDown);
    window.addEventListener("mousemove", canvas.handleCanvasMouseMove);
    window.addEventListener("mouseup", canvas.handleCanvasMouseUp);
    window.addEventListener("mouseleave", canvas.handleCanvasMouseUp);
    canvas.applyCanvasTransform();
  };

  canvas.renderCanvas = function renderCanvas(manifest) {
    canvas.initCanvasInteractions();
    const groupsEl = document.getElementById("canvas-groups");
    const detailsEl = document.getElementById("canvas-details");
    if (!groupsEl || !detailsEl) return;
    state.canvasGroupsEl = groupsEl;
    window.n3CanvasManifest = manifest;
    groupsEl.innerHTML = "";
    const selectedCls = "selected";
    let selectedId = null;
    const layoutResult = layout.computeCanvasLayout(manifest);
    groupsEl.style.width = layoutResult.width ? `${layoutResult.width}px` : "";
    groupsEl.style.height = layoutResult.height ? `${layoutResult.height}px` : "";

    const railsLayer = document.createElement("div");
    railsLayer.className = "canvas-rails";
    const labelsLayer = document.createElement("div");
    labelsLayer.className = "canvas-column-layer";

    layoutResult.columns.forEach((col) => {
      const rail = document.createElement("div");
      rail.className = "canvas-rail";
      rail.style.transform = `translateX(${col.x + col.width / 2}px)`;
      rail.style.height = `${layoutResult.height}px`;
      railsLayer.appendChild(rail);

      const label = document.createElement("div");
      label.className = "canvas-column-label";
      label.style.transform = `translate(${col.x}px, 10px)`;
      label.style.width = `${col.width}px`;
      label.textContent = (N.__canvasKindLabels && N.__canvasKindLabels[col.kind]) || col.kind;
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
        btn.addEventListener("click", () => window.prefillRunnerWithFlow && window.prefillRunnerWithFlow(node.name, true));
        runAction.appendChild(btn);
        detailsEl.appendChild(runAction);
      }
      document.querySelectorAll(".canvas-node").forEach((el) => el.classList.toggle(selectedCls, el.dataset.id === node.id));
      if (state.canvasViewport) {
        const el = document.querySelector(`.canvas-node[data-id=\"${node.id}\"]`);
        if (el) {
          canvas.focusCanvasOnNode(el);
        }
      }
      // Best-effort log note
      N.api.logNote({ event: "canvas_node_clicked", details: { id: node.id, kind: node.kind, name: node.name } }).catch(() => {});
      // Load inspector panel too.
      if (window.loadInspector) window.loadInspector(node.kind, node.name);
      if (node.kind === "flow" && window.prefillRunnerWithFlow) {
        window.prefillRunnerWithFlow(node.name, false);
      }
      if (node.kind === "rag" && window.openRagPipeline) {
        window.openRagPipeline(node.name, true);
      }
    }

    const frag = document.createDocumentFragment();
    frag.appendChild(railsLayer);
    frag.appendChild(labelsLayer);

    layoutResult.nodes.forEach((node) => {
      const shell = document.createElement("div");
      shell.className = "canvas-node-shell";
      shell.style.transform = `translate(${node.x}px, ${node.y}px)`;
      shell.style.width = `${node.width}px`;
      shell.style.height = `${node.height}px`;
      const nodeEl = document.createElement("div");
      nodeEl.className = "canvas-node";
      nodeEl.dataset.id = node.id;
      nodeEl.title = `${node.kind}: ${node.name}`;
      nodeEl.innerHTML = `<div class=\"canvas-node-title\">${N.utils.escapeHtml(node.name)}</div><div class=\"canvas-node-kind\">${N.utils.escapeHtml((N.__canvasKindLabels && N.__canvasKindLabels[node.kind]) || node.kind)}</div>`;
      nodeEl.addEventListener("click", () => showDetails(node));
      shell.appendChild(nodeEl);
      frag.appendChild(shell);
    });

    groupsEl.appendChild(frag);

    canvas.applyCanvasTransform();

    if (!manifest.nodes || !manifest.nodes.length) {
      detailsEl.textContent = manifest.status === "error" ? `Canvas unavailable: ${manifest.error || "unknown error"}` : "No entities found.";
    } else {
      detailsEl.textContent = "Select a node to view details.";
    }
  };

  canvas.loadCanvas = async function loadCanvas() {
    const detailsEl = document.getElementById("canvas-details");
    if (detailsEl) detailsEl.textContent = "Loading canvas…";
    try {
      const data = await N.api.fetchCanvas();
      canvas.renderCanvas(data);
      if (window.populateInspectorEntities) {
        window.populateInspectorEntities(data);
      }
      if (window.setStatus) window.setStatus("Canvas loaded.");
    } catch (err) {
      if (detailsEl) detailsEl.textContent = `Canvas failed: ${err.message}`;
      if (window.setStatus) window.setStatus("Canvas failed to load.", true);
    }
  };
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
