(function (N) {
  const render = (N.render = N.render || {});
  const layout = (render.layout = render.layout || {});
  const state = N.state || {};

  layout.applyCanvasConstants = function applyCanvasConstants() {
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

    N.__canvasKindOrder = CANVAS_KIND_ORDER;
    N.__canvasKindLabels = CANVAS_KIND_LABELS;
    N.__canvasNodeSizes = CANVAS_NODE_SIZES;
    layout.CANVAS_KIND_ORDER = CANVAS_KIND_ORDER;
    layout.CANVAS_KIND_LABELS = CANVAS_KIND_LABELS;
    layout.CANVAS_NODE_SIZES = CANVAS_NODE_SIZES;
  };

  // Apply constants on load to match legacy behavior.
  layout.applyCanvasConstants();

  layout.canvasNodeSize = function canvasNodeSize(kind) {
    const sizes = N.__canvasNodeSizes || {};
    return sizes[kind] || sizes.default;
  };

  layout.canvasLerp = function canvasLerp(a, b, t) {
    if (!Number.isFinite(a)) return b;
    return a + (b - a) * t;
  };

  layout.canvasHash = function canvasHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i += 1) {
      hash = (hash * 31 + str.charCodeAt(i)) | 0;
    }
    return Math.abs(hash);
  };

  layout.canvasManifestSignature = function canvasManifestSignature(manifest) {
    const ids = ((manifest && manifest.nodes) || []).map((n) => n.id || "").sort().join("|");
    const edges = ((manifest && manifest.edges) || [])
      .map((e) => `${e.from || ""}>${e.to || ""}:${e.kind || ""}`)
      .sort()
      .join("|");
    return `${layout.canvasHash(ids)}-${layout.canvasHash(edges)}-${(manifest && manifest.nodes ? manifest.nodes.length : 0)}`;
  };

  layout.canvasProjectKey = function canvasProjectKey() {
    const path = (window.location && window.location.pathname) || "namel3ss";
    const host = (window.location && window.location.host) || "local";
    return `n3_canvas_layout_v1_${host}_${path}`.replace(/[^a-z0-9:_-]/gi, "_");
  };

  layout.readCanvasLayoutCache = function readCanvasLayoutCache(projectKey) {
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
  };

  layout.writeCanvasLayoutCache = function writeCanvasLayoutCache(projectKey, signature, nodes) {
    try {
      localStorage.setItem(projectKey, JSON.stringify({ signature, nodes, layout_version: 1 }));
    } catch (err) {
      // ignore cache write errors
    }
  };

  layout.resolveCanvasCollisions = function resolveCanvasCollisions(columns, gap, topPadding) {
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
  };

  layout.applyCanvasBarycenter = function applyCanvasBarycenter(columns, edges, nodeById, mode) {
    const { canvasLerp } = layout;
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
  };

  layout.computeCanvasLayout = function computeCanvasLayout(manifest) {
    const { canvasNodeSize, canvasProjectKey, canvasManifestSignature, readCanvasLayoutCache, writeCanvasLayoutCache, applyCanvasBarycenter, resolveCanvasCollisions } =
      layout;
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
    const order = N.__canvasKindOrder || [];
    const columnKinds = [...order.filter((k) => kindsPresent.has(k)), ...[...kindsPresent].filter((k) => !order.includes(k)).sort()];
    if (!columnKinds.length) {
      const emptyHeight = state.presentationMode ? 420 : 340;
      return { nodes: [], columns: [], width: 0, height: emptyHeight };
    }
    const columnIndex = {};
    columnKinds.forEach((kind, idx) => {
      columnIndex[kind] = idx;
    });
    const columnWidth = 240;
    const columnGap = state.presentationMode ? 220 : 180;
    const rowGap = state.presentationMode ? 30 : 22;
    const topPadding = state.presentationMode ? 52 : 40;
    const sidePadding = 48;
    const minHeight = state.presentationMode ? 420 : 340;
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
  };
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
