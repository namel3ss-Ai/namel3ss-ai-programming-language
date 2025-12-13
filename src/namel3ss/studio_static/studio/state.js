(function (N) {
  // Shared mutable state for Studio UI.
  N.state = N.state || {};

  N.state.applyDefaults = function applyDefaults() {
    const state = N.state;
    state.loadedPanels = state.loadedPanels || new Set();
    state.pendingRunnerFlow = state.pendingRunnerFlow || null;
    state.pendingMemoryAi = state.pendingMemoryAi || null;
    state.pendingMemorySession = state.pendingMemorySession || null;
    state.pendingAskContext = state.pendingAskContext || null;
    state.currentTheme = state.currentTheme || "light";
    state.pendingAiCall = state.pendingAiCall || null;
    state.flowRunHistory = state.flowRunHistory || [];
    state.commandPaletteOpen = state.commandPaletteOpen || false;
    state.commandItems = state.commandItems || [];
    state.commandFiltered = state.commandFiltered || [];
    state.commandSelectedIndex = state.commandSelectedIndex || 0;
    state.ragPipelineCache = state.ragPipelineCache || [];
    state.canvasScale = state.canvasScale || 1;
    state.canvasOffset = state.canvasOffset || { x: 0, y: 0 };
    state.isCanvasPanning = state.isCanvasPanning || false;
    state.canvasPanStart = state.canvasPanStart || { x: 0, y: 0 };
    state.canvasViewport = state.canvasViewport || null;
    state.canvasGroupsEl = state.canvasGroupsEl || null;
    state.presentationMode = state.presentationMode || false;
    state.askMode = state.askMode || "explain";
    state.warningsCache = state.warningsCache || [];
  };

  // Apply defaults immediately on load for safety.
  N.state.applyDefaults();
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
