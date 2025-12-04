import React, { useEffect, useMemo, useState } from "react";
import { ApiClient } from "../api/client";
import {
  AgentTraceSummary,
  AgentTraceDetail,
  AgentTraceStep,
  AgentConversationMessage,
} from "../api/types";
import AgentTraceTabs from "../components/AgentTraceTabs";
import AgentTimeline from "../components/AgentTimeline";
import AgentConversationTree from "../components/AgentConversationTree";
import AgentRolePanel from "../components/AgentRolePanel";
import AgentMemoryView from "../components/AgentMemoryView";
import AgentStepDetail from "../components/AgentStepDetail";

interface Props {
  client: typeof ApiClient;
}

const AgentsDebuggerPanel: React.FC<Props> = ({ client }) => {
  const [traces, setTraces] = useState<AgentTraceSummary[]>([]);
  const [activeTraceId, setActiveTraceId] = useState<string | null>(null);
  const [activeTrace, setActiveTrace] = useState<AgentTraceDetail | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTraces = async () => {
    setError(null);
    try {
      const list = await client.fetchAgentTraces();
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
      const detail = await client.fetchAgentTraceById(id);
      setActiveTrace(detail);
      setSelectedStepId(detail.steps?.[0]?.id ?? null);
      setSelectedMessageId(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTraces();
  }, []);

  useEffect(() => {
    if (activeTraceId) {
      loadTraceDetail(activeTraceId);
    }
  }, [activeTraceId]);

  const selectedStep = useMemo(() => {
    if (!activeTrace || !selectedStepId) return null;
    return activeTrace.steps.find((s) => s.id === selectedStepId) || null;
  }, [activeTrace, selectedStepId]);

  const messages: AgentConversationMessage[] = activeTrace?.messages || [];

  const handleSelectMessage = (id: string) => {
    setSelectedMessageId(id);
    const msg = messages.find((m) => m.id === id);
    if (msg?.related_step_id) {
      setSelectedStepId(msg.related_step_id);
    }
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>Multi-Agent Debugger</h3>
        <div className="actions">
          <button onClick={loadTraces} disabled={loading}>
            Reload
          </button>
        </div>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      <AgentTraceTabs traces={traces} activeTraceId={activeTraceId} onSelectTrace={setActiveTraceId} />
      {loading && <div className="muted">Loading agent runs…</div>}
      {!activeTrace && !loading && <div className="empty-state">No agent runs yet.</div>}
      {activeTrace && (
        <div className="flow-debugger" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <div>
            <AgentTimeline steps={activeTrace.steps} selectedStepId={selectedStepId} onSelectStep={setSelectedStepId} />
            <div style={{ marginTop: 12 }}>
              <AgentConversationTree
                messages={messages}
                selectedMessageId={selectedMessageId}
                onSelectMessage={handleSelectMessage}
              />
            </div>
          </div>
          <div>
            <AgentRolePanel trace={activeTrace} selectedStep={selectedStep} />
            <AgentMemoryView steps={activeTrace.steps} selectedStepId={selectedStepId} />
            <AgentStepDetail step={selectedStep} />
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentsDebuggerPanel;
