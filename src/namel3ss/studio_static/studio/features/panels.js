(function (N) {
  N.features = N.features || {};
  const panels = (N.features.panels = N.features.panels || {});
  let ctx = null;

  function activatePanel(panel) {
    const state = (ctx && ctx.state) || N.state || {};
    document.querySelectorAll(".studio-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.panel === panel);
    });
    document.querySelectorAll("section.panel").forEach((sec) => {
      sec.classList.toggle("active", sec.id === `panel-${panel}`);
    });
    if (!state.loadedPanels.has(panel)) {
      state.loadedPanels.add(panel);
      switch (panel) {
        case "overview":
          if (typeof window.loadOverview === "function") window.loadOverview();
          break;
        case "run":
          if (typeof window.loadStudioFlows === "function") window.loadStudioFlows();
          break;
        case "traces":
          if (typeof window.loadTraces === "function") window.loadTraces();
          break;
        case "memory":
          if (typeof window.loadMemory === "function") window.loadMemory();
          break;
        case "ask":
          if (typeof window.renderAskContext === "function") window.renderAskContext();
          break;
        case "ai-call":
          if (state.pendingAiCall && typeof window.loadAiCall === "function") {
            window.loadAiCall(state.pendingAiCall.ai, state.pendingAiCall.session);
          }
          break;
        case "rag":
          if (typeof window.loadRagPipelinesList === "function") window.loadRagPipelinesList();
          if (typeof window.runRagQuery === "function") window.runRagQuery();
          break;
        case "diagnostics":
          if (typeof window.runDiagnostics === "function") window.runDiagnostics();
          break;
        default:
          break;
      }
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
      "overview-reload": window.loadOverview,
      "traces-reload": window.loadTraces,
      "memory-refresh": window.loadMemory,
      "rag-run": window.runRagQuery,
      "rag-load": window.loadRagPipelinesList,
      "diagnostics-run": window.runDiagnostics,
      "run-app": window.runApp,
      "run-flow": window.runFlow,
      "flow-runner-refresh": window.loadStudioFlows,
      "flow-runner-run": window.runStudioFlow,
      "ask-run": window.runAskStudio,
      "logs-clear": () => window.renderLogs && window.renderLogs([]),
      "canvas-reload": window.loadCanvas,
      "inspector-load": () => {
        const kind = document.getElementById("inspector-kind")?.value;
        const name = document.getElementById("inspector-entity")?.value;
        if (window.loadInspector) window.loadInspector(kind, name);
      },
      "reparse-now": window.reparseNow,
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
        if (window.populateInspectorEntities) window.populateInspectorEntities(window.n3CanvasManifest || {});
      });
    }
    const memorySelect = document.getElementById("memory-ai-select");
    if (memorySelect) {
      memorySelect.addEventListener("change", () => window.loadMemoryDetails && window.loadMemoryDetails(memorySelect.value));
    }

    document.querySelectorAll(".theme-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const theme = btn.dataset.theme || "light";
        if (window.setTheme) window.setTheme(theme);
      });
    });

    const historySelect = document.getElementById("flow-run-history");
    if (historySelect) {
      historySelect.addEventListener("change", () => {
        if (historySelect.value && window.selectHistoryRun) {
          window.selectHistoryRun(historySelect.value);
        }
      });
    }

    const presentationBtn = document.getElementById("presentation-toggle");
    if (presentationBtn) {
      presentationBtn.addEventListener("click", () => window.togglePresentationMode && window.togglePresentationMode());
    }

    document.querySelectorAll(".ask-mode-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (window.setAskMode) window.setAskMode(btn.dataset.mode || "explain");
      });
    });

    const warningsBtn = document.getElementById("warnings-toggle");
    if (warningsBtn) {
      warningsBtn.addEventListener("click", () => window.toggleWarningsPanel && window.toggleWarningsPanel());
    }
  }

  function onDomReady() {
    initTabs();
    initButtons();
    activatePanel("overview");
    if (window.loadProviderStatus) window.loadProviderStatus();
    if (window.loadStudioStatus) window.loadStudioStatus();
    if (window.connectLogsStream) window.connectLogsStream();
    if (window.loadCanvas) window.loadCanvas();
    if (window.renderRunHistory) window.renderRunHistory();
    if (window.setStatus) window.setStatus("Ready.");
  }

  function handleKeydown(event) {
    if (!((ctx && ctx.state && ctx.state.commandPaletteOpen) || (N.state && N.state.commandPaletteOpen)) && event.shiftKey && event.key.toLowerCase() === "p") {
      const tag = (document.activeElement && document.activeElement.tagName) || "";
      if (!["INPUT", "TEXTAREA"].includes(tag)) {
        event.preventDefault();
        if (window.togglePresentationMode) window.togglePresentationMode();
      }
    }
  }

  panels.init = function initPanels(context) {
    ctx = context || ctx;
    document.addEventListener("DOMContentLoaded", onDomReady);
    document.addEventListener("keydown", handleKeydown);
  };

  panels.activatePanel = activatePanel;
  panels.initTabs = initTabs;
  panels.initButtons = initButtons;
  panels.onDomReady = onDomReady;
  panels.handleKeydown = handleKeydown;
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
