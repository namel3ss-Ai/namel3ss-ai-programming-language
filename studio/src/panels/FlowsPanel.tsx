import React, { useState } from "react";
import { ApiClient } from "../api/client";
import { FlowSummary, TriggerSummary } from "../api/types";

interface Props {
  code: string;
  client: typeof ApiClient;
}

const FlowsPanel: React.FC<Props> = ({ code, client }) => {
  const [flows, setFlows] = useState<FlowSummary[]>([]);
  const [triggers, setTriggers] = useState<TriggerSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const flowRes = await client.fetchFlows(code);
      setFlows(flowRes.flows);
      const trigRes = await client.fetchTriggers();
      setTriggers(trigRes.triggers);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fireTrigger = async (id: string) => {
    setMessage(null);
    try {
      const res = await client.fireTrigger(id, {});
      setMessage(res.job_id ? `Fired trigger ${id}` : `Trigger ${id} disabled`);
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="panel" aria-label="flows-panel">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>Flows & Automations</h3>
        <button onClick={load} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {message && <div style={{ color: "green" }}>{message}</div>}
      <div style={{ display: "flex", gap: "1rem" }}>
        <div style={{ flex: 1 }}>
          <h4>Flows</h4>
          {flows.length === 0 ? (
            <div>No flows detected.</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Steps</th>
                </tr>
              </thead>
              <tbody>
                {flows.map((flow) => (
                  <tr key={flow.name}>
                    <td>{flow.name}</td>
                    <td>{flow.description || "-"}</td>
                    <td>{flow.steps}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div style={{ flex: 1 }}>
          <h4>Automations</h4>
          {triggers.length === 0 ? (
            <div>No triggers registered.</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Kind</th>
                  <th>Flow</th>
                  <th>Last Fired</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {triggers.map((trigger) => (
                  <tr key={trigger.id}>
                    <td>{trigger.id}</td>
                    <td>{trigger.kind}</td>
                    <td>{trigger.flow_name}</td>
                    <td>{trigger.last_fired || "never"}</td>
                    <td>
                      <button onClick={() => fireTrigger(trigger.id)} disabled={loading || !trigger.enabled}>
                        Fire
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

export default FlowsPanel;
