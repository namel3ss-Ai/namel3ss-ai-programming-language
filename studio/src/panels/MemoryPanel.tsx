import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ApiClient } from "../api/client";
import {
  MemoryPlanResponse,
  MemoryPolicyInfo,
  MemoryRecallRule,
  MemorySessionInfo,
  MemoryStateResponse,
} from "../api/types";
import { useApi } from "../hooks/useApi";

interface Props {
  client: typeof ApiClient;
}

const KIND_TITLES: Record<string, string> = {
  short_term: "Short-Term",
  long_term: "Long-Term",
  episodic: "Episodic",
  semantic: "Semantic",
  profile: "Profile",
};

const formatRetentionLabel = (value?: number | null) => {
  if (!value) {
    return "not set";
  }
  return `${value} day${value === 1 ? "" : "s"}`;
};

const formatHalfLife = (value?: number | null) => {
  if (!value) {
    return null;
  }
  return `${value} day${value === 1 ? "" : "s"}`;
};

const MemoryPanel: React.FC<Props> = ({ client }) => {
  const { data: summary, loading: summaryLoading, error: summaryError } = useApi(() => client.fetchStudioSummary(), []);
  const aiNames = useMemo(() => (summary?.summary?.ai_calls as string[] | undefined) || [], [summary]);
  const [selectedAi, setSelectedAi] = useState<string>("");

  const [sessions, setSessions] = useState<MemorySessionInfo[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [sessionsRefreshKey, setSessionsRefreshKey] = useState(0);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);

  const [plan, setPlan] = useState<MemoryPlanResponse | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);

  const [stateTarget, setStateTarget] = useState<{ sessionId?: string | null; userId?: string | null } | null>(null);
  const [stateData, setStateData] = useState<MemoryStateResponse | null>(null);
  const [stateLoading, setStateLoading] = useState(false);
  const [stateError, setStateError] = useState<string | null>(null);
  const [stateRefreshKey, setStateRefreshKey] = useState(0);

  const [userInput, setUserInput] = useState("");

  useEffect(() => {
    if (!selectedAi && aiNames.length > 0) {
      setSelectedAi(aiNames[0]);
    } else if (selectedAi && !aiNames.includes(selectedAi)) {
      setSelectedAi(aiNames[0] || "");
    }
  }, [aiNames, selectedAi]);

  useEffect(() => {
    setSessions([]);
    setSelectedSession(null);
    setStateTarget(null);
    setStateData(null);
    setStateError(null);
  }, [selectedAi]);

  useEffect(() => {
    if (!selectedAi) {
      setPlan(null);
      return;
    }
    setPlanLoading(true);
    setPlanError(null);
    client
      .fetchMemoryPlan(selectedAi)
      .then((res) => setPlan(res))
      .catch((err: Error) => setPlanError(err.message))
      .finally(() => setPlanLoading(false));
  }, [client, selectedAi]);

  useEffect(() => {
    if (!selectedAi) {
      setSessions([]);
      setSessionsError(null);
      return;
    }
    setSessionsLoading(true);
    setSessionsError(null);
    client
      .fetchMemorySessions(selectedAi)
      .then((res) => {
        const fetched = res.sessions || [];
        setSessions(fetched);
        setSelectedSession((prev) => {
          if (prev && fetched.some((entry) => entry.id === prev)) {
            return prev;
          }
          const fallback = fetched[0]?.id ?? null;
          setStateTarget((current) => {
            if (current && current.userId) {
              return current;
            }
            if (!fallback) {
              return null;
            }
            if (current && current.sessionId === fallback) {
              return current;
            }
            return { sessionId: fallback };
          });
          return fallback;
        });
      })
      .catch((err: Error) => setSessionsError(err.message))
      .finally(() => setSessionsLoading(false));
  }, [client, selectedAi, sessionsRefreshKey]);

  useEffect(() => {
    if (!selectedAi || !stateTarget) {
      setStateData(null);
      setStateLoading(false);
      return;
    }
    setStateLoading(true);
    setStateError(null);
    client
      .fetchMemoryState(selectedAi, { ...stateTarget, limit: 50 })
      .then((res) => setStateData(res))
      .catch((err: Error) => setStateError(err.message))
      .finally(() => setStateLoading(false));
  }, [client, selectedAi, stateTarget, stateRefreshKey]);

  const refreshSessions = useCallback(() => {
    setSessionsRefreshKey((prev) => prev + 1);
  }, []);

  const refreshState = useCallback(() => {
    if (!stateTarget) {
      return;
    }
    setStateRefreshKey((prev) => prev + 1);
  }, [stateTarget]);

  const handleInspectUser = useCallback(() => {
    const trimmed = userInput.trim();
    if (!trimmed) {
      return;
    }
    setSelectedSession(null);
    setStateTarget({ userId: trimmed });
  }, [userInput]);

  const handleSessionClick = useCallback((sessionId: string) => {
    setSelectedSession(sessionId);
    setStateTarget({ sessionId });
  }, []);

  const currentPolicies = stateData?.policies || {};
  const stateKinds = stateData?.kinds || {};
  const recallRules = plan?.recall ?? [];
  const snapshot = stateData?.recall_snapshot;
  const snapshotRules = snapshot?.rules ?? [];
  const snapshotMessages = snapshot?.messages ?? [];
  const snapshotDiagnostics = snapshot?.diagnostics ?? [];

  return (
    <div className="panel memory-panel" aria-label="memory-panel">
      <h3>Memory Inspector</h3>
      {summaryLoading && <div>Loading project summary...</div>}
      {summaryError && <div style={{ color: "red" }}>{summaryError}</div>}
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 12 }}>
        <label style={{ fontWeight: 500 }}>AI</label>
        <select
          value={selectedAi}
          onChange={(e) => setSelectedAi(e.target.value)}
          disabled={aiNames.length === 0}
          style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #cbd5f5" }}
        >
          {aiNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <button onClick={refreshSessions} disabled={!selectedAi || sessionsLoading}>
          Refresh Sessions
        </button>
        <button onClick={refreshState} disabled={!stateTarget || stateLoading}>
          Reload View
        </button>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="text"
            value={userInput}
            placeholder="user-123"
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleInspectUser();
              }
            }}
            style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #cbd5f5" }}
          />
          <button onClick={handleInspectUser} disabled={!userInput.trim()}>
            Inspect User
          </button>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 16, minHeight: 360 }}>
        <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Sessions</div>
          <p style={{ fontSize: 12, color: "#64748b", marginTop: 0 }}>
            Pick a session for per-session scopes or enter a user id to inspect shared/per-user kinds.
          </p>
          {sessionsLoading && <div>Loading sessions...</div>}
          {sessionsError && <div style={{ color: "red" }}>{sessionsError}</div>}
          {sessions.length === 0 && !sessionsLoading && <div style={{ color: "#94a3b8" }}>No sessions yet.</div>}
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {sessions.map((session) => (
              <li key={session.id}>
                <button
                  className={session.id === selectedSession ? "list-item selected" : "list-item"}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    padding: "6px 8px",
                    borderRadius: 6,
                    border: "none",
                    background: session.id === selectedSession ? "#e0f2fe" : "transparent",
                    cursor: "pointer",
                  }}
                  onClick={() => handleSessionClick(session.id)}
                >
                  <div style={{ fontWeight: 500 }}>{session.id}</div>
                  <div style={{ fontSize: 12, color: "#64748b" }}>
                    Turns: {session.turns}{" "}
                    {session.last_activity ? `• ${new Date(session.last_activity).toLocaleString()}` : null}
                  </div>
                  {session.user_id && <div style={{ fontSize: 12, color: "#94a3b8" }}>User: {session.user_id}</div>}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 12, overflowY: "auto" }}>
          <Section title="Configuration Summary">
            {planLoading && <div>Loading plan...</div>}
            {planError && <div style={{ color: "red" }}>{planError}</div>}
            {!planLoading && !planError && plan && plan.kinds.length === 0 && (
              <div style={{ color: "#94a3b8" }}>This AI has no memory configured.</div>
            )}
            {plan &&
              plan.kinds.map((entry) => (
                <div key={entry.kind} className="card" style={{ marginBottom: 8, padding: 12 }}>
                  <div style={{ fontWeight: 600 }}>
                    {KIND_TITLES[entry.kind] || entry.kind} {entry.enabled ? "— Enabled" : "— Disabled"}
                  </div>
                  <div>Scope: {entry.scope || "default"}</div>
                  <div>Retention: {formatRetentionLabel(entry.retention_days)}</div>
                  <div>PII Policy: {entry.pii_policy || "none"}</div>
                  {typeof entry.window === "number" && <div>Window: {entry.window}</div>}
                  {entry.store && <div>Store: {entry.store}</div>}
                  {entry.time_decay?.half_life_days && (
                    <div>Time Decay Half-Life: {formatHalfLife(entry.time_decay.half_life_days)}</div>
                  )}
                  {entry.pipeline && entry.pipeline.length > 0 && (
                    <div style={{ marginTop: 6 }}>
                      <div style={{ fontWeight: 500 }}>Pipeline</div>
                      <ul style={{ margin: 0, paddingLeft: 18 }}>
                        {entry.pipeline.map((step) => (
                          <li key={step.name}>
                            <strong>{step.name}</strong> — {step.type}
                            {step.target_kind ? ` → ${step.target_kind}` : ""}
                            {step.max_tokens ? ` (max ${step.max_tokens})` : ""}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
          </Section>
          <Section title="Recall Plan">
            {!plan || recallRules.length === 0 ? (
              <div style={{ color: "#94a3b8" }}>No recall rules defined.</div>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {recallRules.map((rule, idx) => (
                  <li key={`${rule.source || "rule"}-${idx}`}>
                    <strong>{rule.source || "unknown"}</strong>
                    {typeof rule.count === "number" ? ` • count ${rule.count}` : null}
                    {typeof rule.top_k === "number" ? ` • top_k ${rule.top_k}` : null}
                    {rule.include === false ? " • skipped" : null}
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section title="Memory State">
            {!stateTarget && <div style={{ color: "#94a3b8" }}>Select a session or enter a user id to inspect state.</div>}
            {stateError && <div style={{ color: "red" }}>{stateError}</div>}
            {stateLoading && <div>Loading memory...</div>}
            {stateTarget && stateData && (
              <>
                <div style={{ marginBottom: 12 }}>
                  {stateData.session_id && (
                    <div>
                      <strong>Session:</strong> {stateData.session_id}
                    </div>
                  )}
                  {stateData.user_id && (
                    <div style={{ color: "#64748b" }}>
                      <strong>User ID:</strong> {stateData.user_id}
                    </div>
                  )}
                </div>
                {stateKinds.short_term && (
                  <KindSection title="Short-Term">
                    <PolicySummary info={currentPolicies.short_term} />
                    {stateKinds.short_term.turns.length === 0 && <div>No turns recorded.</div>}
                    {stateKinds.short_term.turns.map((turn, idx) => (
                      <div key={`${turn.role}-${idx}`} style={{ marginBottom: 8 }}>
                        <div style={{ fontWeight: 600 }}>{turn.role}</div>
                        <div>{turn.content}</div>
                        {turn.created_at && <div style={{ fontSize: 12, color: "#94a3b8" }}>{turn.created_at}</div>}
                      </div>
                    ))}
                  </KindSection>
                )}
                {stateKinds.long_term && (
                  <ItemsSection title="Long-Term" items={stateKinds.long_term.items} policy={currentPolicies.long_term} />
                )}
                {stateKinds.episodic && (
                  <ItemsSection title="Episodic" items={stateKinds.episodic.items} policy={currentPolicies.episodic} />
                )}
                {stateKinds.semantic && (
                  <ItemsSection title="Semantic" items={stateKinds.semantic.items} policy={currentPolicies.semantic} />
                )}
                {stateKinds.profile && (
                  <KindSection title="Profile Facts">
                    <PolicySummary info={currentPolicies.profile} />
                    {stateKinds.profile.facts.length === 0 && <div>No stored facts.</div>}
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {stateKinds.profile.facts.map((fact, idx) => (
                        <li key={`${fact}-${idx}`}>{fact}</li>
                      ))}
                    </ul>
                  </KindSection>
                )}
                {!stateKinds.short_term &&
                  !stateKinds.long_term &&
                  !stateKinds.episodic &&
                  !stateKinds.semantic &&
                  !stateKinds.profile && <div style={{ color: "#94a3b8" }}>No memory entries for this context.</div>}
              </>
            )}
          </Section>
          {snapshot && (
            <Section title="Last Recall Snapshot">
              <div style={{ fontSize: 12, color: "#94a3b8" }}>{snapshot.timestamp}</div>
              <div style={{ marginTop: 8 }}>
                <strong>Rules:</strong>
                <ul style={{ margin: "4px 0 8px", paddingLeft: 18 }}>
                  {snapshotRules.map((rule, idx) => (
                    <li key={`recall-rule-${idx}`}>
                      {rule.source}
                      {typeof rule.count === "number" ? ` • count ${rule.count}` : null}
                      {typeof rule.top_k === "number" ? ` • top_k ${rule.top_k}` : null}
                      {rule.include === false ? " • skipped" : null}
                    </li>
                  ))}
                </ul>
              </div>
              {snapshotDiagnostics.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <strong>Diagnostics:</strong>
                  <ul style={{ margin: "4px 0", paddingLeft: 18 }}>
                    {snapshotDiagnostics.map((diag, idx) => (
                      <li key={`diag-${idx}`}>
                        {diag.kind || "kind"} — selected {diag.selected ?? 0}
                        {diag.scope ? ` (${diag.scope})` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div>
                <strong>Messages:</strong>
                <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                  {snapshotMessages.map((msg, idx) => (
                    <li key={`msg-${idx}`}>
                      <strong>{msg.role}</strong>: {msg.content}
                    </li>
                  ))}
                </ul>
              </div>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
};

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div style={{ marginBottom: 16 }}>
    <h4 style={{ marginBottom: 8 }}>{title}</h4>
    {children}
  </div>
);

const KindSection: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div style={{ marginBottom: 12 }}>
    <h5 style={{ margin: "8px 0" }}>{title}</h5>
    {children}
  </div>
);

const ItemsSection: React.FC<{
  title: string;
  items: { summary?: string | null; content?: string | null; created_at?: string | null; decay_score?: number | null; id?: string | number | null }[];
  policy?: MemoryPolicyInfo | null;
}> = ({ title, items, policy }) => (
  <KindSection title={title}>
    <PolicySummary info={policy} />
    {items.length === 0 && <div>No {title.toLowerCase()} entries.</div>}
    {items.map((item, idx) => (
      <div key={(item.id as string | number | undefined) ?? `${title}-${idx}`} className="card" style={{ marginBottom: 8, padding: 8 }}>
        <div style={{ fontWeight: 600 }}>{item.summary || item.content || "(no summary)"}</div>
        {item.created_at && <div style={{ fontSize: 12, color: "#94a3b8" }}>{item.created_at}</div>}
        {typeof item.decay_score === "number" && (
          <div style={{ fontSize: 12, color: "#64748b" }}>Decay score: {item.decay_score.toFixed(3)}</div>
        )}
      </div>
    ))}
  </KindSection>
);

const PolicySummary: React.FC<{ info?: MemoryPolicyInfo | null }> = ({ info }) => {
  if (!info) {
    return null;
  }
  return (
    <div style={{ fontSize: 12, color: "#475569", marginBottom: 8 }}>
      <div>
        Scope: {info.scope}
        {info.scope_fallback ? " (fallback)" : ""}
      </div>
      <div>Retention: {formatRetentionLabel(info.retention_days)}</div>
      <div>PII Policy: {info.pii_policy}</div>
      {info.time_decay?.half_life_days && <div>Time Decay Half-Life: {formatHalfLife(info.time_decay.half_life_days)}</div>}
      {info.scope_note && <div style={{ color: "#b45309" }}>{info.scope_note}</div>}
    </div>
  );
};

export default MemoryPanel;
