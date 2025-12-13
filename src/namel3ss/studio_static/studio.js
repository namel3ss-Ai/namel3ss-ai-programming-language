(() => {
  // Loader and namespace shim (stage 1). Keeps behavior identical while enabling optional modular splits.
  const __current = document.currentScript && document.currentScript.src;
  const __base = __current ? __current.substring(0, __current.lastIndexOf("/") + 1) : "/studio/";
  const __ns = (window.N3_STUDIO = window.N3_STUDIO || {});
  __ns.__version = "shim-1";
  __ns.__base = __base;
  __ns.__loaded = __ns.__loaded || {};
  __ns.api = __ns.api || {};
  __ns.utils = __ns.utils || {};
  __ns.state = __ns.state || {};
  __ns.render = __ns.render || {};
  __ns.log = __ns.log || ((...args) => console.debug("[Studio]", ...args));

  // Optional tiny fallback for escapeHtml.
  if (!__ns.utils.escapeHtml) {
    __ns.utils.escapeHtml = function (value) {
      return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    };
  }

  __ns.loadScripts = function (files) {
    if (!files || !files.length) return Promise.resolve();
    return files.reduce((p, file) => {
      return p.then(
        () =>
          new Promise((resolve, reject) => {
            const s = document.createElement("script");
            s.src = __base + file;
            s.async = false;
            s.onload = () => resolve();
            s.onerror = (e) => reject(e);
            document.head.appendChild(s);
          })
      );
    }, Promise.resolve());
  };

  // Stage 2: load noop placeholders via the loader (does not change behavior).
  __ns.loadScripts([
    "studio/utils.js",
    "studio/api.js",
    "studio/state.js",
    "studio/dom.js",
    "studio/render/layout.js",
    "studio/render/canvas.js",
    "studio/features/panels.js",
    "studio/features/commands.js",
    "studio/features/flows.js",
    "studio/features/ask.js",
    "studio/features/rag.js",
    "studio/features/diagnostics.js",
    "studio/features/traces.js",
    "studio/features/memory.js",
    "studio/features/files.js",
    "studio/features/preferences.js",
    "studio/features/status.js",
    "studio/panels/explorer.js",
    "studio/panels/inspector.js",
    "studio/panels/console.js",
    "studio/bootstrap.js",
  ]).then(() => {
    __ns.__loaded.utils = true;
    __ns.__loaded.api = true;
    __ns.__loaded.state = true;
    __ns.__loaded.dom = true;
    __ns.__loaded.render = true;
    __ns.__loaded.panels = true;
  });

  const state = window.N3_STUDIO.state;
  // Ensure defaults exist even before the state module loads.
  if (window.N3_STUDIO && window.N3_STUDIO.state && typeof window.N3_STUDIO.state.applyDefaults === "function") {
    window.N3_STUDIO.state.applyDefaults();
  } else {
    state.loadedPanels = state.loadedPanels || new Set();
    state.flowRunHistory = state.flowRunHistory || [];
    state.commandPaletteOpen = state.commandPaletteOpen || false;
    state.askMode = state.askMode || "explain";
    state.currentTheme = state.currentTheme || "light";
  }

  if (
    window.N3_STUDIO &&
    window.N3_STUDIO.render &&
    window.N3_STUDIO.render.layout &&
    typeof window.N3_STUDIO.render.layout.applyCanvasConstants === "function"
  ) {
    window.N3_STUDIO.render.layout.applyCanvasConstants();
  }

  const f = (__ns.features = __ns.features || {});
  const panels = (__ns.panels = __ns.panels || {});
  const render = (__ns.render = __ns.render || {});
  const getApiKey = () => __ns.api.getApiKey();
  const escapeHtml = (v) => __ns.utils.escapeHtml(v);
  const setStatus = (m, e = false) => {
    const el = document.getElementById("studio-status");
    if (!el) return;
    el.textContent = m;
    el.classList.toggle("status-error", !!e);
  };
  const clamp = (v, min, max) => __ns.utils.clamp(v, min, max);
  const formatLogLine = (entry) => __ns.utils.formatLogLine(entry);
  const renderLogs = (entries) => panels.console.renderLogs(entries);
  const connectLogsStream = () => panels.console.connectLogsStream();
  const formatDurationSeconds = (v) => __ns.utils.formatDurationSeconds(v);
  const formatTimestamp = (ts) => __ns.utils.formatTimestamp(ts);
  const canvasNodeSize = (k) => render.layout.canvasNodeSize(k);
  const canvasLerp = (a, b, t) => render.layout.canvasLerp(a, b, t);
  const canvasHash = (str) => render.layout.canvasHash(str);
  const canvasManifestSignature = (m) => render.layout.canvasManifestSignature(m);
  const canvasProjectKey = () => render.layout.canvasProjectKey();
  const readCanvasLayoutCache = (key) => render.layout.readCanvasLayoutCache(key);
  const writeCanvasLayoutCache = (key, sig, nodes) => render.layout.writeCanvasLayoutCache(key, sig, nodes);
  const applyCanvasTransform = () => render.canvas.applyCanvasTransform();
  const handleCanvasWheel = (e) => render.canvas.handleCanvasWheel(e);
  const handleCanvasMouseDown = (e) => render.canvas.handleCanvasMouseDown(e);
  const handleCanvasMouseMove = (e) => render.canvas.handleCanvasMouseMove(e);
  const handleCanvasMouseUp = () => render.canvas.handleCanvasMouseUp();
  const focusCanvasOnNode = (el) => render.canvas.focusCanvasOnNode(el);
  const initCanvasInteractions = () => render.canvas.initCanvasInteractions();
  const renderCanvas = (manifest) => render.canvas.renderCanvas(manifest);
  const loadCanvas = () => render.canvas.loadCanvas();
  const renderInspector = (data) => panels.inspector?.render?.(data);
  const prefillRunnerWithFlow = (...a) => f.flows?.prefillRunnerWithFlow?.(...a);
  const prefillMemory = (...a) => f.memory?.prefillMemory?.(...a);
  const prefillAsk = (question, ctx = null, activate = false, mode = null) => {
    const qEl = document.getElementById("ask-question");
    if (qEl && question) qEl.value = question;
    state.pendingAskContext = ctx;
    if (mode) setAskMode(mode);
    if (activate) {
      activatePanel("ask");
      renderAskContext();
    }
  };
  const renderMemoryPlan = (...a) => f.memory?.renderMemoryPlan?.(...a);
  const renderMemorySessions = (...a) => f.memory?.renderMemorySessions?.(...a);
  const renderTurns = (...a) => f.memory?.renderTurns?.(...a) ?? "<div>No short-term history.</div>";
  const renderItems = (...a) => f.memory?.renderItems?.(...a) ?? "<div>No entries.</div>";
  const renderRecallSnapshot = (...a) => f.memory?.renderRecallSnapshot?.(...a) ?? "<div>No recall snapshot.</div>";
  const renderMemoryState = (...a) => f.memory?.renderMemoryState?.(...a);
  const renderAiCall = (...a) => f.memory?.renderAiCall?.(...a);
  const loadAiCall = (...a) => f.memory?.loadAiCall?.(...a);
  const openAiCallVisualizer = (...a) => f.memory?.openAiCallVisualizer?.(...a);
  const openRagPipeline = (...a) => f.rag?.openRagPipeline?.(...a);
  const addRunToHistory = (...a) => f.flows?.addRunToHistory?.(...a);
  const renderRunHistory = (...a) => f.flows?.renderRunHistory?.(...a);
  const selectHistoryRun = (...a) => f.flows?.selectHistoryRun?.(...a);
  const loadMemoryDetails = (...a) => f.memory?.loadMemoryDetails?.(...a) ?? Promise.resolve();
  const loadMemoryState = (...a) => f.memory?.loadMemoryState?.(...a) ?? Promise.resolve();
  const loadMemoryAIs = (...a) => f.memory?.loadMemoryAIs?.(...a) ?? Promise.resolve();
  const renderAskContext = () => f.ask?.renderAskContext?.();
  const runAskStudio = (...a) => f.ask?.runAskStudio?.(...a);
  const loadStudioFlows = (...a) => f.flows?.loadStudioFlows?.(...a) ?? Promise.resolve();
  const renderFlowRunResult = (...a) => f.flows?.renderFlowRunResult?.(...a);
  const runStudioFlow = (...a) => f.flows?.runStudioFlow?.(...a);
  const loadInspector = (...a) => panels.inspector?.load?.(...a);
  const populateInspectorEntities = (...a) => panels.inspector?.populateEntities?.(...a);
  const renderBanner = (message, tone = "warn") => {
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
  const jsonRequest = (url, options = {}) => __ns.api.jsonRequest(url, options);
  const renderJsonIn = (id, data) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (data === undefined || data === null) {
      el.textContent = "No data.";
      return;
    }
    el.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  };
  const loadWarnings = () => panels.console.loadWarnings();
  const renderWarningsIndicator = () => panels.console.renderWarningsIndicator();
  const goToWarning = (w) => panels.console.goToWarning(w);
  const renderWarningsPanel = (t) => panels.console.renderWarningsPanel(t);
  const toggleWarningsPanel = (fShow) => panels.console.toggleWarningsPanel(fShow);
  const closeCommandPalette = () => f.commands?.closeCommandPalette?.();
  const openCommandPalette = () => f.commands?.openCommandPalette?.();
  const toggleCommandPalette = () => f.commands?.toggleCommandPalette?.();
  const loadRagPipelinesList = (...a) => f.rag?.loadRagPipelinesList?.(...a) ?? Promise.resolve();
  const loadRagPipeline = (...a) => f.rag?.loadRagPipeline?.(...a) ?? Promise.resolve();
  const renderRagPipeline = (...a) => f.rag?.renderRagPipeline?.(...a);
  const reparseNow = (...a) => f.status?.reparseNow?.(...a) ?? Promise.resolve();
  const ensureCommandsBuilt = () => f.commands?.ensureCommandsBuilt?.();
  const renderCommandResults = () => f.commands?.renderCommandResults?.();
  const executeSelectedCommand = () => f.commands?.executeSelectedCommand?.();
  const loadProviderStatus = (...a) => f.status?.loadProviderStatus?.(...a) ?? Promise.resolve();
  const loadStudioStatus = (...a) => f.status?.loadStudioStatus?.(...a) ?? Promise.resolve();
  const activatePanel = (panel) => f.panels?.activatePanel?.(panel);
  const loadOverview = async () => {
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
  };
  const runApp = (...a) => f.files?.runApp?.(...a);
  const runFlow = (...a) => f.files?.runFlow?.(...a);
  const loadTraces = (...a) => f.traces?.loadTraces?.(...a) ?? Promise.resolve();
  const loadMemory = (...a) => f.memory?.loadMemory?.(...a);
  const runRagQuery = (...a) => f.rag?.runRagQuery?.(...a) ?? Promise.resolve();
  const runDiagnostics = (...a) => f.diagnostics?.runDiagnostics?.(...a) ?? Promise.resolve();
  const initTabs = () => f.panels?.initTabs?.();
  const initButtons = () => f.panels?.initButtons?.();
  const setTheme = (...a) => f.preferences?.setTheme?.(...a);
  const initTheme = (...a) => f.preferences?.initTheme?.(...a);
  const setAskMode = (...a) => f.preferences?.setAskMode?.(...a);
  const initAskMode = (...a) => f.preferences?.initAskMode?.(...a);
  const renderAskSnippets = (...a) => f.ask?.renderAskSnippets?.(...a);
  const setPresentationMode = (...a) => f.preferences?.setPresentationMode?.(...a);
  const togglePresentationMode = (...a) => f.preferences?.togglePresentationMode?.(...a);
  const initPresentationMode = (...a) => f.preferences?.initPresentationMode?.(...a);

  if (window.N3_STUDIO && typeof window.N3_STUDIO.startStudio === "function") {
    window.N3_STUDIO.startStudio();
  } else {
    initTheme();
    initAskMode();
    initPresentationMode();
    loadWarnings();
  }
})();
