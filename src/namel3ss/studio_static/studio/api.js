(function (N) {
  const api = (N.api = N.api || {});

  api.getApiKey = function getApiKey() {
    const el = document.getElementById("api-key-input");
    return el ? el.value.trim() : "";
  };

  api.jsonRequest = async function jsonRequest(url, options = {}) {
    const headers = options.headers ? { ...options.headers } : {};
    if (options.body) {
      headers["Content-Type"] = "application/json";
    }
    const apiKey = api.getApiKey();
    if (apiKey) {
      headers["X-API-Key"] = apiKey;
    }
    const resp = await fetch(url, { ...options, headers });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`${resp.status} ${resp.statusText}: ${text || "No response body"}`);
    }
    const contentType = resp.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return resp.json();
    }
    return resp.text();
  };

  api.streamLogs = function streamLogs() {
    return fetch("/api/studio/logs/stream");
  };

  api.logNote = function logNote(payload) {
    return fetch("/api/studio/log-note", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
  };
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
