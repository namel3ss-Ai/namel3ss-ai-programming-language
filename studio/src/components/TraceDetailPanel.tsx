import React, { useEffect, useMemo, useState } from "react";
import type { TraceDetail, TraceEvent } from "../api/types";
import { ApiClient } from "../api/client";
import { ConditionList } from "./ConditionList";
import { normalizeConditions } from "../trace/conditions";

export interface TraceDetailPanelProps {
  traceId: string | null;
  onClose: () => void;
}

export const TraceDetailPanel: React.FC<TraceDetailPanelProps> = ({ traceId, onClose }) => {
  const [detail, setDetail] = useState<TraceDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);

  useEffect(() => {
    if (!traceId) {
      setDetail(null);
      setSelectedStepId(null);
      setErrorMessage(null);
      setIsLoading(false);
      return;
    }
    let cancelled = false;
    async function loadDetail() {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const res = await ApiClient.fetchTraceById(traceId);
        if (!cancelled) {
          setDetail(res as any);
          const firstStepId = res.events && res.events.length > 0 ? res.events[0].id : null;
          setSelectedStepId(firstStepId);
        }
      } catch (err) {
        if (!cancelled) {
          setErrorMessage("Failed to load trace");
          setDetail(null);
          setSelectedStepId(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }
    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [traceId]);

  if (!traceId) {
    return null;
  }

  const steps: TraceEvent[] = (detail?.events ?? []).map((event) => ({
    ...event,
    name: event.kind || event.message || event.id,
  }));
  const selectedStep = steps.find((s) => s.id === selectedStepId) ?? (steps[0] ?? null);
  const conditions = useMemo(() => normalizeConditions(detail?.events ?? []), [detail]);

  return (
    <div className="n3-trace-detail-panel">
      <div className="n3-trace-detail-header">
        <h3>Trace Detail</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      {isLoading && <div className="n3-trace-detail-loading">Loading trace...</div>}
      {errorMessage && <div className="n3-trace-detail-error">{errorMessage}</div>}
      {!isLoading && !errorMessage && detail && (
        <div className="n3-trace-detail-body">
          <div className="n3-trace-detail-meta">
            <div>ID: {detail.id}</div>
            {detail.flow_name && <div>Flow: {detail.flow_name}</div>}
            {detail.status && <div>Status: {detail.status}</div>}
            {detail.started_at && <div>Started at: {String(detail.started_at)}</div>}
          </div>
          <div className="n3-trace-detail-main">
            <div className="n3-trace-steps-list">
              <h4>Steps</h4>
              {steps.length === 0 ? (
                <div>No steps in this trace.</div>
              ) : (
                <ul>
                  {steps.map((step) => (
                    <li
                      key={step.id}
                      className={
                        "n3-trace-step-item" + (step.id === selectedStep?.id ? " n3-trace-step-item-active" : "")
                      }
                    >
                      <button type="button" onClick={() => setSelectedStepId(step.id)}>
                        {step.name || step.id}
                        {step.status ? ` (${step.status})` : ""}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="n3-trace-step-detail">
              <h4>Step Detail</h4>
              {!selectedStep && <div>No step selected.</div>}
              {selectedStep && (
                <div>
                  <div>ID: {selectedStep.id}</div>
                  {selectedStep.name && <div>Name: {selectedStep.name}</div>}
                  {selectedStep.kind && <div>Kind: {selectedStep.kind}</div>}
                  {selectedStep.status && <div>Status: {selectedStep.status}</div>}
                  {selectedStep.timestamp && <div>Timestamp: {String(selectedStep.timestamp)}</div>}
                  <pre className="n3-trace-step-detail-json">
                    <code>{JSON.stringify(selectedStep, null, 2)}</code>
                  </pre>
                </div>
              )}
            </div>
          </div>
          <ConditionList conditions={conditions} />
        </div>
      )}
    </div>
  );
};
