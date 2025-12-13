(function (N) {
  N.features = N.features || {};
  const ask = (N.features.ask = N.features.ask || {});
  let ctx = null;

  function getState() {
    return (ctx && ctx.state) || N.state || {};
  }

  function getUtils() {
    return (ctx && ctx.utils) || N.utils || {};
  }

  function renderAskSnippets(snippets) {
    const utils = getUtils();
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
            <div class="snippet-kind">${utils.escapeHtml((s.kind || "snippet").toUpperCase())}</div>
            <div class="snippet-title">${utils.escapeHtml(s.title || "Suggested snippet")}</div>
            <button class="snippet-copy" data-dsl-index="${idx}">Copy</button>
            <code>${utils.escapeHtml(s.dsl || "")}</code>
            ${s.notes ? `<div class="snippet-notes">${utils.escapeHtml(s.notes || "")}</div>` : ""}
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

  function renderAskContext() {
    const state = getState();
    const ctxEl = document.getElementById("ask-context");
    if (!ctxEl) return;
    if (!state.pendingAskContext) {
      ctxEl.textContent = "No extra context set.";
      return;
    }
    ctxEl.textContent = `Context: ${JSON.stringify(state.pendingAskContext, null, 2)}`;
  }

  async function runAskStudio() {
    const state = getState();
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
      if (state.pendingAskContext) body.context = state.pendingAskContext;
      body.mode = state.askMode || "explain";
      const resp = await N.api.jsonRequest("/api/studio/ask", { method: "POST", body: JSON.stringify(body) });
      if (ansEl) {
        ansEl.classList.remove("revealed");
        ansEl.textContent = resp.answer || "(no answer)";
        void ansEl.offsetWidth;
        ansEl.classList.add("revealed");
      }
      renderAskSnippets(resp.suggested_snippets || []);
      if (typeof window.setStatus === "function") window.setStatus("Ask Studio answered.");
    } catch (err) {
      if (ansEl) ansEl.textContent = "Ask Studio is currently unavailable. Check provider configuration or try again later.";
      if (typeof window.setStatus === "function") window.setStatus("Ask Studio failed.", true);
    }
  }

  ask.init = function initAsk(context) {
    ctx = context || ctx;
    return undefined;
  };

  ask.runAskStudio = runAskStudio;
  ask.renderAskSnippets = renderAskSnippets;
  ask.renderAskContext = renderAskContext;
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
