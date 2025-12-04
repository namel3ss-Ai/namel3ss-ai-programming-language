import React, { useEffect, useMemo, useState } from "react";
import { ApiClient } from "../api/client";
import {
  FlowSummary,
  TriggerSummary,
  TraceSummary,
  TraceDetail,
  FlowNode,
  TraceEvent,
} from "../api/types";
import TraceTabs from "../components/TraceTabs";
import FlowGraphView from "../components/FlowGraphView";
import FlowStepList from "../components/FlowStepList";
import FlowStepDetails from "../components/FlowStepDetails";

interface Props {
  code: string;
  client: typeof ApiClient;
}

const FlowsPanel: React.FC<Props> = ({ code, client }) => {
  const [flows, setFlows] = useState<FlowSummary[]>([]);
  const [triggers, setTriggers] = useState<TriggerSummary[]>([]);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [activeTraceId, setActiveTraceId] = useState<string | null>(null);
  const [activeTrace, setActiveTrace] = useState<TraceDetail | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadFlowsAndTriggers = async () => {
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

  const loadTraces = async () => {
    setError(null);
    try {
      const list = await client.fetchTraces();
      setTraces(list);
      if (list.length > 0 && !activeTraceId) {
        setActiveTraceId(list[0].id);
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  const loadTraceDetail = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const trace = await client.fetchTraceById(id);
      setActiveTrace(trace);
      setSelectedNodeId(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFlowsAndTriggers();
    loadTraces();
  }, []);

  useEffect(() => {
    if (activeTraceId) {
      loadTraceDetail(activeTraceId);
    }
  }, [activeTraceId]);

  const fireTrigger = async (id: string) => {
    setMessage(null);
    try {
      const res = await client.fireTrigger(id, {});
      setMessage(res.job_id ? `Fired trigger ${id}` : `Trigger ${id} disabled`);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const graph = useMemo(() => {
    if (activeTrace?.graph) return activeTrace.graph;
    const flowsTrace = activeTrace?.trace?.flows;
    if (flowsTrace && flowsTrace.length > 0) {
      const steps = flowsTrace[0].steps || [];
      const nodes: FlowNode[] = steps.map((step: any, idx: number) => ({
        id: step.node_id || `step-${idx}`,
        label: step.step_name || `step-${idx}`,
        kind: step.kind || "step",
      }));
      const edges = nodes.slice(1).map((node, idx) => ({
        from: nodes[idx].id,
        to: node.id,
      }));
      return { nodes, edges };
    }
    return { nodes: [], edges: [] };
  }, [activeTrace]);

  const events: TraceEvent[] | undefined = useMemo(() => {
    if (activeTrace?.events) return activeTrace.events;
    const flowsTrace = activeTrace?.trace?.flows;
    if (flowsTrace && flowsTrace.length > 0) {
      return flowsTrace[0].events || [];
    }
    return [];
  }, [activeTrace]);

  const selectedNode = useMemo(
    () => graph.nodes.find((n) => n.id === selectedNodeId) || null,
    [graph.nodes, selectedNodeId]
  );

  const eventsForNode = useMemo(() => {
    if (!selectedNodeId) return [];
    return (events || []).filter((e) => e.node_id === selectedNodeId);
  }, [events, selectedNodeId]);

  return (
    <div className="panel" aria-label="flows-panel">
      <div className="panel-head">
        <h3>Flow Debugger</h3>
        <div className="actions">
          <button onClick={loadTraces} disabled={loading}>
            Reload Traces
          </button>
        </div>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      <TraceTabs traces={traces} activeTraceId={activeTraceId} onSelectTrace={setActiveTraceId} />
      {activeTrace ? (
        <div className="flow-debugger">
          <div className="flow-graph">
            <FlowGraphView graph={graph} selectedNodeId={selectedNodeId} onSelectNode={setSelectedNodeId} />
          </div>
          <div className="flow-details">
            <FlowStepDetails trace={activeTrace} selectedNode={selectedNode} eventsForNode={eventsForNode} />
          </div>
        </div>
      ) : (
        <div>No traces yet. Trigger a flow or app run to see traces.</div>
      )}
      <div className="flow-step-list">
        <FlowStepList graph={graph} events={events} selectedNodeId={selectedNodeId} onSelectNode={setSelectedNodeId} />
      </div>

      <hr />

      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>Flows & Automations</h3>
        <button onClick={loadFlowsAndTriggers} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
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
