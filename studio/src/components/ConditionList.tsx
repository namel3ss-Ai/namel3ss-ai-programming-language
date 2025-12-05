import React from "react";
import type { NormalizedCondition } from "../trace/conditions";

export interface ConditionListProps {
  conditions: NormalizedCondition[];
}

const scopeLabel = (scope: string) => (scope === "agent" ? "AGENT" : "FLOW");

const ResultBadge: React.FC<{ taken: boolean }> = ({ taken }) => (
  <span className={`n3-cond-result ${taken ? "n3-cond-true" : "n3-cond-false"}`}>{taken ? "True" : "False"}</span>
);

const Pill: React.FC<{ label: string; className?: string }> = ({ label, className }) => (
  <span className={`n3-pill ${className ?? ""}`.trim()}>{label}</span>
);

export const ConditionList: React.FC<ConditionListProps> = ({ conditions }) => {
  if (!conditions.length) {
    return (
      <section className="n3-conditions">
        <h4>Conditions</h4>
        <div className="n3-cond-empty">No conditions evaluated in this trace.</div>
      </section>
    );
  }

  return (
    <section className="n3-conditions">
      <h4>Conditions</h4>
      <div className="n3-cond-list">
        {conditions.map((cond) => (
          <div key={cond.id} className="n3-cond-row">
            <div className="n3-cond-main">
              <div className="n3-cond-expression">
                {cond.expression || cond.rulegroup || cond.patternSummary || "Condition"}
              </div>
              <div className="n3-cond-meta">
                <Pill label={scopeLabel(cond.scope)} className="n3-pill-scope" />
                {cond.kind === "pattern" && <Pill label="PATTERN" className="n3-pill-kind" />}
                {cond.kind === "rulegroup" && <Pill label="RULEGROUP" className="n3-pill-kind" />}
                {cond.macro && <Pill label={`MACRO ${cond.macro}`} className="n3-pill-kind" />}
                {cond.rulegroup && cond.ruleName && <Pill label={cond.ruleName} className="n3-pill-kind" />}
              </div>
            </div>
            <div className="n3-cond-side">
              <ResultBadge taken={cond.taken} />
              {cond.bindingName && (
                <div className="n3-cond-binding">
                  {cond.bindingName}: {String(cond.bindingValue)}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
