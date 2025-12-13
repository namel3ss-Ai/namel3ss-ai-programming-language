(function (N) {
  N.features = N.features || {};
  const prefs = (N.features.preferences = N.features.preferences || {});

  prefs.setTheme = function setTheme(theme) {
    const state = N.state || {};
    state.currentTheme = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = state.currentTheme;
    try {
      localStorage.setItem("n3_studio_theme", state.currentTheme);
    } catch (err) {
      // ignore storage errors
    }
    document.querySelectorAll(".theme-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.theme === state.currentTheme);
    });
  };

  prefs.initTheme = function initTheme() {
    try {
      const stored = localStorage.getItem("n3_studio_theme");
      if (stored) {
        prefs.setTheme(stored);
        return;
      }
    } catch (err) {
      // ignore
    }
    prefs.setTheme("light");
  };

  prefs.setAskMode = function setAskMode(mode) {
    const state = N.state || {};
    state.askMode = mode || "explain";
    document.querySelectorAll(".ask-mode-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mode === state.askMode);
    });
    try {
      localStorage.setItem("n3_studio_ask_mode", state.askMode);
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
      hint.textContent = messages[state.askMode] || messages.explain;
    }
  };

  prefs.initAskMode = function initAskMode() {
    try {
      const stored = localStorage.getItem("n3_studio_ask_mode");
      if (stored) {
        prefs.setAskMode(stored);
        return;
      }
    } catch (err) {
      // ignore
    }
    prefs.setAskMode("explain");
  };

  prefs.setPresentationMode = function setPresentationMode(enabled) {
    const state = N.state || {};
    state.presentationMode = Boolean(enabled);
    document.documentElement.dataset.presentation = state.presentationMode ? "true" : "false";
    try {
      localStorage.setItem("n3_studio_presentation_mode", state.presentationMode ? "true" : "false");
    } catch (err) {
      // ignore
    }
    const btn = document.getElementById("presentation-toggle");
    if (btn) {
      btn.classList.toggle("active", state.presentationMode);
      btn.setAttribute("aria-pressed", state.presentationMode ? "true" : "false");
      btn.textContent = state.presentationMode ? "Presentation On" : "Presentation";
    }
    if (window.n3CanvasManifest && typeof window.renderCanvas === "function") {
      window.renderCanvas(window.n3CanvasManifest);
    }
  };

  prefs.togglePresentationMode = function togglePresentationMode() {
    const state = N.state || {};
    prefs.setPresentationMode(!state.presentationMode);
  };

  prefs.initPresentationMode = function initPresentationMode() {
    try {
      const stored = localStorage.getItem("n3_studio_presentation_mode");
      if (stored === "true") {
        prefs.setPresentationMode(true);
        return;
      }
    } catch (err) {
      // ignore
    }
    prefs.setPresentationMode(false);
  };

  prefs.init = function init(ctx) {
    if (ctx && ctx.state) {
      N.state = ctx.state;
    }
    prefs.initTheme();
    prefs.initAskMode();
    prefs.initPresentationMode();
  };
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
