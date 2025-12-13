(function (N) {
  N.startStudio =
    N.startStudio ||
    function startStudio() {
      if (typeof window.initTheme === "function") window.initTheme();
      if (typeof window.initAskMode === "function") window.initAskMode();
      if (typeof window.initPresentationMode === "function") window.initPresentationMode();
      if (N.features?.preferences?.init) N.features.preferences.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.features?.status?.init) N.features.status.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (typeof window.loadWarnings === "function") window.loadWarnings();
      if (N.features?.panels?.init) N.features.panels.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.features?.commands?.init) N.features.commands.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.features?.flows?.init) N.features.flows.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.features?.ask?.init) N.features.ask.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.features?.rag?.init) N.features.rag.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.features?.files?.init) N.features.files.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.features?.memory?.init) N.features.memory.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.features?.diagnostics?.init) N.features.diagnostics.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.features?.traces?.init) N.features.traces.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.panels?.explorer?.init) N.panels.explorer.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.panels?.inspector?.init) N.panels.inspector.init({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
      if (N.panels?.console?.init) N.panels.console.init?.({ api: N.api, state: N.state, dom: N.dom, utils: N.utils, panels: N.panels, render: N.render, features: N.features });
    };
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
