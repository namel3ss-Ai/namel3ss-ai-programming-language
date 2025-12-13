(function (N) {
  const utils = (N.utils = N.utils || {});

  utils.escapeHtml =
    utils.escapeHtml ||
    function (value) {
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    };

  utils.clamp =
    utils.clamp ||
    function (val, min, max) {
      return Math.min(Math.max(val, min), max);
    };

  utils.formatLogLine =
    utils.formatLogLine ||
    function (entry) {
      const ts = entry.timestamp || "";
      const level = entry.level || "info";
      const event = entry.event || "";
      const details = entry.details || {};
      let detailText = "";
      try {
        detailText = Object.entries(details)
          .map(([k, v]) => `${k}=${v}`)
          .join("  ");
      } catch (err) {
        detailText = "";
      }
      return { ts, level, event, detailText };
    };

  utils.formatDurationSeconds =
    utils.formatDurationSeconds ||
    function (value) {
      if (value == null) return "";
      if (value < 0.001) return `${Math.round(value * 1e6)} µs`;
      if (value < 1) return `${Math.round(value * 1000)} ms`;
      return `${value.toFixed(2)} s`;
    };

  utils.formatTimestamp =
    utils.formatTimestamp ||
    function (ts) {
      if (!ts) return "";
      try {
        return new Date(ts).toLocaleTimeString();
      } catch (err) {
        return ts;
      }
    };
})(window.N3_STUDIO || (window.N3_STUDIO = {}));
