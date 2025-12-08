import React, { useEffect, useMemo, useState } from "react";
import { ApiClient, StreamEvent } from "../api/client";

interface Props {
  code: string;
  client: typeof ApiClient;
}

const RunnerPanel: React.FC<Props> = ({ code, client }) => {
  const [appName, setAppName] = useState("support");
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewState, setPreviewState] = useState<Record<string, any>>({});

  const applyStateChange = useMemo(
    () => (state: Record<string, any>, path: string, value: any) => {
      if (!path) return state;
      const parts = path.split(".");
      const next = { ...state };
      let cursor: any = next;
      for (let i = 0; i < parts.length - 1; i += 1) {
        const key = parts[i];
        const existing = cursor[key];
        cursor[key] = typeof existing === "object" && existing !== null ? { ...existing } : {};
        cursor = cursor[key];
      }
      cursor[parts[parts.length - 1]] = value;
      return next;
    },
    []
  );

  useEffect(() => {
    if (!client.subscribeStateStream) return;
    const stop = client.subscribeStateStream((evt: StreamEvent) => {
      if (evt.event !== "state_change" || !("path" in evt)) return;
      setPreviewState((prev) => applyStateChange(prev, (evt as any).path as string, (evt as any).new_value));
    });
    return () => {
      if (typeof stop === "function") {
        stop();
      }
    };
  }, [applyStateChange, client]);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await client.runApp(code, appName);
      setResult(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel" aria-label="runner-panel">
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <h3>App Runner & UI Preview</h3>
        <input
          value={appName}
          onChange={(e) => setAppName(e.target.value)}
          placeholder="app name"
          style={{ padding: 8, borderRadius: 6, border: "1px solid #e2e8f0" }}
        />
        <button onClick={run} disabled={loading}>
          {loading ? "Running..." : "Run"}
        </button>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {result && (
        <div>
          <h4>Entry Page</h4>
          <pre>{JSON.stringify(result.entry_page, null, 2)}</pre>
          <h4>Graph</h4>
          <pre>{JSON.stringify(result.graph, null, 2)}</pre>
        </div>
      )}
      <div style={{ marginTop: 16 }}>
        <h4>Live State (from /api/ui/state/stream)</h4>
        <pre>{JSON.stringify(previewState, null, 2)}</pre>
      </div>
    </div>
  );
};

export default RunnerPanel;
