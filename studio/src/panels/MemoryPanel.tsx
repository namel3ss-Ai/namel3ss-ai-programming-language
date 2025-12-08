import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ApiClient } from "../api/client";
import { MemoryPolicyInfo, MemorySessionDetail, MemorySessionInfo } from "../api/types";
import { useApi } from "../hooks/useApi";

interface Props {
  client: typeof ApiClient;
}

const MemoryPanel: React.FC<Props> = ({ client }) => {
  const { data: summary, loading: summaryLoading, error: summaryError } = useApi(() => client.fetchStudioSummary(), []);
  const aiNames = useMemo(() => (summary?.summary?.ai_calls as string[] | undefined) || [], [summary]);
  const [selectedAi, setSelectedAi] = useState<string>("");
  const [sessions, setSessions] = useState<MemorySessionInfo[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [detail, setDetail] = useState<MemorySessionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [sessionsRefreshKey, setSessionsRefreshKey] = useState(0);

  useEffect(() => {
    if (!selectedAi && aiNames.length > 0) {
      setSelectedAi(aiNames[0]);
    } else if (selectedAi && !aiNames.includes(selectedAi)) {
      setSelectedAi(aiNames[0] || "");
    }
  }, [aiNames, selectedAi]);

  useEffect(() => {
    if (!selectedAi) {
      setSessions([]);
      setSelectedSession(null);
      setDetail(null);
      return;
    }
    setSessionsLoading(true);
    setSessionsError(null);
    client
      .fetchMemorySessions(selectedAi)
      .then((res) => {
        const fetched = res.sessions || [];
        setSessions(fetched);
        if (fetched.length === 0) {
          setSelectedSession(null);
          setDetail(null);
          return;
        }
        setSelectedSession((prev) => {
          if (prev && fetched.some((s) => s.id === prev)) {
            return prev;
          }
          return fetched[0].id;
        });
      })
      .catch((err: Error) => setSessionsError(err.message))
      .finally(() => setSessionsLoading(false));
  }, [client, selectedAi, sessionsRefreshKey]);

  useEffect(() => {
    if (!selectedAi || !selectedSession) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    setDetailError(null);
    client
      .fetchMemorySessionDetail(selectedAi, selectedSession)
      .then((res) => setDetail(res))
      .catch((err: Error) => setDetailError(err.message))
      .finally(() => setDetailLoading(false));
  }, [client, selectedAi, selectedSession]);

  const refreshSessions = useCallback(() => {
    setSessionsRefreshKey((prev) => prev + 1);
  }, []);

  const handleClear = useCallback(
    async (kinds?: string[]) => {
      if (!selectedAi || !selectedSession) {
        return;
      }
      const label = kinds && kinds.length ? kinds.join(", ") : "all";
      const confirmed = window.confirm(`Clear ${label} memory for session ${selectedSession}?`);
      if (!confirmed) {
        return;
      }
      await client.clearMemorySession(selectedAi, selectedSession, kinds);
      setDetail(null);
      refreshSessions();
    },
    [client, refreshSessions, selectedAi, selectedSession],
  );

  return (
    <div className="panel memory-panel" aria-label="memory-panel">
      <h3>Memory Inspector</h3>
      {summaryLoading && <div>Loading project summary...</div>}
      {summaryError && <div style={{ color: "red" }}>{summaryError}</div>}
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
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
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 16, minHeight: 320 }}>
        <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 8 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Sessions</div>
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
                  onClick={() => setSelectedSession(session.id)}
                >
                  <div style={{ fontWeight: 500 }}>{session.id}</div>
                  <div style={{ fontSize: 12, color: "#64748b" }}>
                    Turns: {session.turns} {session.last_activity ? `• ${new Date(session.last_activity).toLocaleString()}` : null}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 12 }}>
          {!selectedSession && <div>Select a session to inspect memory.</div>}
          {detailLoading && <div>Loading memory...</div>}
          {detailError && <div style={{ color: "red" }}>{detailError}</div>}
          {detail && selectedSession && (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <div>
                  <strong>Session:</strong> {detail.session}
                  {detail.user_id && (
                    <div style={{ fontSize: 12, color: "#94a3b8" }}>
                      User ID: {detail.user_id}
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={() => handleClear()} style={{ background: "#fee2e2" }}>
                    Clear All
                  </button>
                  <button onClick={() => handleClear(["long_term"])} style={{ background: "#fef3c7" }}>
                    Clear Long-Term
                  </button>
                </div>
              </div>
              <Section title="Conversation">
                <PolicySummary info={detail.policies?.short_term} />
                {detail.short_term.turns.length === 0 && <div>No turns recorded.</div>}
                {detail.short_term.turns.map((turn, idx) => (
                  <div key={idx} style={{ marginBottom: 8 }}>
                    <div style={{ fontWeight: 600 }}>{turn.role}</div>
                    <div>{turn.content}</div>
                    {turn.created_at && <div style={{ fontSize: 12, color: "#94a3b8" }}>{turn.created_at}</div>}
                  </div>
                ))}
              </Section>
              {detail.long_term && (
                <Section title="Long-Term Memory">
                  <PolicySummary info={detail.policies?.long_term} />
                  {detail.long_term.items.length === 0 && <div>No long-term items.</div>}
                  {detail.long_term.items.map((item) => (
                    <div key={item.id} className="card" style={{ marginBottom: 8 }}>
                      <div style={{ fontWeight: 600 }}>{item.summary}</div>
                      {item.created_at && <div style={{ fontSize: 12, color: "#94a3b8" }}>{item.created_at}</div>}
                    </div>
                  ))}
                </Section>
              )}
              {detail.profile && (
                <Section title="Profile Facts">
                  <PolicySummary info={detail.policies?.profile} />
                  {detail.profile.facts.length === 0 && <div>No stored facts.</div>}
                  <ul>
                    {detail.profile.facts.map((fact, idx) => (
                      <li key={idx}>{fact}</li>
                    ))}
                  </ul>
                </Section>
              )}
              {detail.last_recall_snapshot && (
                <Section title="Last Recall Snapshot">
                  <div style={{ fontSize: 12, color: "#94a3b8" }}>{detail.last_recall_snapshot.timestamp}</div>
                  <div style={{ marginBottom: 8 }}>
                    <strong>Rules:</strong>{" "}
                    {detail.last_recall_snapshot.rules.map((rule, idx) => (
                      <span key={idx}>
                        {rule.source}
                        {rule.count ? ` count=${rule.count}` : ""}
                        {rule.top_k ? ` top_k=${rule.top_k}` : ""}
                        {rule.include === false ? " (skip)" : ""}{" "}
                      </span>
                    ))}
                  </div>
                  <div>
                    <strong>Messages:</strong>
                    <ul>
                      {detail.last_recall_snapshot.messages.map((msg, idx) => (
                        <li key={idx}>
                          <strong>{msg.role}</strong>: {msg.content}
                        </li>
                      ))}
                    </ul>
                  </div>
                </Section>
              )}
            </>
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

const PolicySummary: React.FC<{ info?: MemoryPolicyInfo | null }> = ({ info }) => {
  if (!info) {
    return null;
  }
  const retentionLabel =
    info.retention_days && info.retention_days > 0 ? `${info.retention_days} day${info.retention_days === 1 ? "" : "s"}` : "not set";
  return (
    <div style={{ fontSize: 12, color: "#475569", marginBottom: 8 }}>
      <div>
        Scope: {info.scope}
        {info.scope_fallback ? " (fallback)" : ""}
      </div>
      <div>Retention: {retentionLabel}</div>
      <div>PII Policy: {info.pii_policy}</div>
      {info.scope_note && <div style={{ color: "#b45309" }}>{info.scope_note}</div>}
    </div>
  );
};

export default MemoryPanel;
