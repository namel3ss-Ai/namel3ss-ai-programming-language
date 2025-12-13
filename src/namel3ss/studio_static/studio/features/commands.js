(function (N) {
  N.features = N.features || {};
  const commands = (N.features.commands = N.features.commands || {});
  let ctx = null;

  function closeCommandPalette() {
    const state = (ctx && ctx.state) || N.state || {};
    const overlay = document.getElementById("command-palette-overlay");
    if (!overlay) return;
    overlay.classList.add("hidden");
    state.commandPaletteOpen = false;
    state.commandSelectedIndex = 0;
    const input = document.getElementById("command-input");
    if (input) input.value = "";
    renderCommandResults();
  }

  function openCommandPalette() {
    const state = (ctx && ctx.state) || N.state || {};
    const overlay = document.getElementById("command-palette-overlay");
    const input = document.getElementById("command-input");
    if (!overlay || !input) return;
    overlay.classList.remove("hidden");
    state.commandPaletteOpen = true;
    ensureCommandsBuilt();
    renderCommandResults();
    requestAnimationFrame(() => input.focus());
  }

  function toggleCommandPalette() {
    const state = (ctx && ctx.state) || N.state || {};
    if (state.commandPaletteOpen) {
      closeCommandPalette();
    } else {
      openCommandPalette();
    }
  }

  function buildCommandListFromCanvas() {
    const state = (ctx && ctx.state) || N.state || {};
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
          if (window.prefillRunnerWithFlow) window.prefillRunnerWithFlow(name, true);
        };
      } else if (kind === "rag") {
        label = `View RAG pipeline: ${name}`;
        hint = "rag pipeline";
        action = () => window.openRagPipeline && window.openRagPipeline(name, true);
      } else {
        label = `Inspect ${kind}: ${name}`;
        action = () => {
          if (window.activatePanel) window.activatePanel("inspector");
          if (window.loadInspector) window.loadInspector(kind, name);
        };
      }
      state.commandItems.push({ id, label, hint, run: action });
    });
  }

  function buildCommandListStatic() {
    const state = (ctx && ctx.state) || N.state || {};
    const panels = [
      { id: "panel:overview", label: "Open Overview", hint: "panel", run: () => window.activatePanel && window.activatePanel("overview") },
      { id: "panel:canvas", label: "Open Canvas", hint: "panel", run: () => window.activatePanel && window.activatePanel("canvas") },
      { id: "panel:inspector", label: "Open Inspector", hint: "panel", run: () => window.activatePanel && window.activatePanel("inspector") },
      { id: "panel:run", label: "Open Flow Runner", hint: "panel", run: () => window.activatePanel && window.activatePanel("run") },
      { id: "panel:memory", label: "Open Memory Viewer", hint: "panel", run: () => window.activatePanel && window.activatePanel("memory") },
      { id: "panel:rag", label: "Open RAG Pipelines", hint: "panel", run: () => window.activatePanel && window.activatePanel("rag") },
      { id: "panel:logs", label: "Open Logs", hint: "panel", run: () => window.activatePanel && window.activatePanel("logs") },
      { id: "panel:ai-call", label: "Open AI Call Visualizer", hint: "panel", run: () => window.activatePanel && window.activatePanel("ai-call") },
      { id: "panel:ask", label: "Open Ask Studio", hint: "panel", run: () => window.activatePanel && window.activatePanel("ask") },
      { id: "command:reparse", label: "Re-Parse Now", hint: "command", run: () => window.reparseNow && window.reparseNow() },
    ];
    state.commandItems.push(...panels);
  }

  function buildCommandListFlows() {
    const state = (ctx && ctx.state) || N.state || {};
    const select = document.getElementById("flow-runner-name");
    if (!select || !select.options) return;
    Array.from(select.options)
      .map((opt) => opt.value)
      .filter(Boolean)
      .forEach((flow) => {
        state.commandItems.push({
          id: `flow:${flow}`,
          label: `Run flow: ${flow}`,
          hint: "flow",
          run: () => window.prefillRunnerWithFlow && window.prefillRunnerWithFlow(flow, true),
        });
      });
  }

  function buildCommandListRag() {
    const state = (ctx && ctx.state) || N.state || {};
    (state.ragPipelineCache || []).forEach((name) => {
      state.commandItems.push({
        id: `rag:${name}`,
        label: `View RAG pipeline: ${name}`,
        hint: "rag",
        run: () => window.openRagPipeline && window.openRagPipeline(name, true),
      });
    });
  }

  function ensureCommandsBuilt() {
    const state = (ctx && ctx.state) || N.state || {};
    state.commandItems = [];
    buildCommandListStatic();
    buildCommandListFromCanvas();
    buildCommandListFlows();
    buildCommandListRag();
    state.commandFiltered = [...state.commandItems];
  }

  function renderCommandResults() {
    const state = (ctx && ctx.state) || N.state || {};
    const container = document.getElementById("command-results");
    const input = document.getElementById("command-input");
    if (!container) return;
    const query = (input && input.value.trim().toLowerCase()) || "";
    if (!query) {
      state.commandFiltered = [...state.commandItems];
    } else {
      state.commandFiltered = state.commandItems.filter((cmd) => cmd.label.toLowerCase().includes(query));
    }
    if (state.commandSelectedIndex >= state.commandFiltered.length) state.commandSelectedIndex = 0;
    const html = state.commandFiltered
      .map(
        (cmd, idx) =>
          `<div class="command-item ${idx === state.commandSelectedIndex ? "active" : ""}" data-id="${cmd.id}">
            <span>${N.utils.escapeHtml(cmd.label)}</span>
            <span class="hint">${N.utils.escapeHtml(cmd.hint || "")}</span>
          </div>`
      )
      .join("");
    container.innerHTML = html || '<div class="command-item">No commands</div>';
    container.querySelectorAll(".command-item").forEach((el, idx) => {
      el.addEventListener("click", () => {
        state.commandSelectedIndex = idx;
        executeSelectedCommand();
      });
    });
  }

  function executeSelectedCommand() {
    const state = (ctx && ctx.state) || N.state || {};
    const cmd = state.commandFiltered[state.commandSelectedIndex];
    if (!cmd || !cmd.run) return;
    cmd.run();
    closeCommandPalette();
  }

  function handleKeydown(event) {
    const state = (ctx && ctx.state) || N.state || {};
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      toggleCommandPalette();
      return;
    }
    if (!state.commandPaletteOpen) return;
    if (event.key === "Escape") {
      closeCommandPalette();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      state.commandSelectedIndex = Math.min(state.commandSelectedIndex + 1, (state.commandFiltered.length || 1) - 1);
      renderCommandResults();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      state.commandSelectedIndex = Math.max(state.commandSelectedIndex - 1, 0);
      renderCommandResults();
    } else if (event.key === "Enter") {
      event.preventDefault();
      executeSelectedCommand();
    }
  }

  function initOverlayAndInput() {
    const state = (ctx && ctx.state) || N.state || {};
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
        state.commandSelectedIndex = 0;
        renderCommandResults();
      });
    }
  }

  commands.init = function initCommands(context) {
    ctx = context || ctx;
    document.addEventListener("keydown", handleKeydown);
    document.addEventListener("DOMContentLoaded", initOverlayAndInput);
  };

  commands.closeCommandPalette = closeCommandPalette;
  commands.openCommandPalette = openCommandPalette;
  commands.toggleCommandPalette = toggleCommandPalette;
  commands.ensureCommandsBuilt = ensureCommandsBuilt;
  commands.renderCommandResults = renderCommandResults;
  commands.executeSelectedCommand = executeSelectedCommand;
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
