(function (N) {
  const panels = (N.panels = N.panels || {});
  const explorer = (panels.explorer = panels.explorer || {});

  explorer.init = function initExplorer() {
    // Explorer currently uses legacy inline logic in studio.js; this placeholder ensures init ordering.
    if (typeof window.renderCanvas === "function") {
      // no-op; explorer UI is static for now.
    }
  };

  explorer.render = function renderExplorer(manifest) {
    if (typeof window.renderCanvas === "function" && manifest) {
      window.renderCanvas(manifest);
    }
  };
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
