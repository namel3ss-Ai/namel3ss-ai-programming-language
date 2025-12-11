import React, { useEffect, useState } from "react";
import { ApiClient } from "../api/client";
import { StudioRunsResponse, StudioTraceResponse } from "../api/types";

interface Props {
  client: typeof ApiClient;
}

const TracePanel: React.FC<Props> = ({ client }) => {
  const [runs, setRuns] = useState<StudioRunsResponse["runs"]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [trace, setTrace] = useState<StudioTraceResponse["trace"] | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    refreshRuns();
  }, []);

  const refreshRuns = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await client.fetchStudioRuns();
      setRuns(res.runs || []);
      if (res.runs && res.runs.length > 0) {
        loadTrace(res.runs[0].run_id);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadTrace = async (runId: string) => {
    setSelectedRun(runId);
    setError(null);
    try {
      const res = await client.fetchStudioTrace(runId);
      setTrace(res.trace || []);
      setSelectedEvent((res.trace || [])[0] || null);
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="panel" aria-label="trace-panel">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>Run timeline</h3>
        <button onClick={refreshRuns} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      <div style={{ display: "flex", gap: "1rem" }}>
        <div style={{ minWidth: 240 }}>
          <h4>Runs</h4>
          <ul>
            {runs.map((run) => (
              <li key={run.run_id}>
                <button
                  onClick={() => loadTrace(run.run_id)}
                  style={{ fontWeight: selectedRun === run.run_id ? "bold" : "normal" }}
                >
                  {run.label || run.run_id.slice(0, 6)} ({run.status || "unknown"})
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div style={{ flex: 1 }}>
          {trace && trace.length > 0 ? (
            <div style={{ display: "flex", gap: "1rem" }}>
              <div style={{ flex: 1 }}>
                <h4>Timeline</h4>
                <ul>
                  {trace.map((evt: any) => (
                    <li key={evt.span_id}>
                      <button
                        onClick={() => setSelectedEvent(evt)}
                        style={{ fontWeight: selectedEvent?.span_id === evt.span_id ? "bold" : "normal" }}
                      >
                        [{evt.kind}] {evt.name} {evt.duration ? `${evt.duration.toFixed(3)}s` : ""}
                        {evt.exception ? " ⚠" : ""}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
              <div style={{ flex: 1 }}>
                <h4>Details</h4>
                {selectedEvent ? (
                  <pre style={{ maxHeight: 300, overflow: "auto" }}>{JSON.stringify(selectedEvent, null, 2)}</pre>
                ) : (
                  <div>Select an event to inspect.</div>
                )}
              </div>
            </div>
          ) : (
            <div>No trace available.</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TracePanel;
