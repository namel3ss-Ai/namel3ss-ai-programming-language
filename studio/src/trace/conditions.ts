import type {
  ConditionEvalEvent,
  FlowGotoEvent,
  PatternConditionEvalEvent,
  RuleGroupConditionEvalEvent,
  TraceEvent,
} from "../api/types";

export type NormalizedConditionKind = "simple" | "pattern" | "rulegroup";

export interface NormalizedCondition {
  id: string;
  scope: "flow" | "agent";
  kind: NormalizedConditionKind;
  expression?: string;
  macro?: string;
  rulegroup?: string;
  ruleName?: string;
  patternSummary?: string;
  result: boolean;
  taken: boolean;
  bindingName?: string;
  bindingValue?: unknown;
  stepName?: string;
  flowName?: string;
  timestamp?: string;
}

const isConditionEvent = (event: TraceEvent): event is ConditionEvalEvent => {
  const name = (event.event || event.kind || "").toString();
  return name.includes("condition.eval");
};

const isPatternEvent = (event: TraceEvent): event is PatternConditionEvalEvent => {
  const name = (event.event || event.kind || "").toString();
  return name.includes("condition.pattern.eval");
};

const isRuleGroupEvent = (event: TraceEvent): event is RuleGroupConditionEvalEvent => {
  const name = (event.event || event.kind || "").toString();
  return name.includes("condition.rulegroup.eval");
};

export const normalizeConditions = (events: TraceEvent[] | undefined | null): NormalizedCondition[] => {
  if (!events || events.length === 0) {
    return [];
  }
  const normalized: NormalizedCondition[] = [];

  events.forEach((event, idx) => {
    const scope = (event.scope === "agent" || event.scope === "flow" ? event.scope : undefined) ?? "flow";
    const baseId = event.id || `${event.event || event.kind || "evt"}-${idx}`;
    if (isPatternEvent(event)) {
      const patternSummary =
        event.pattern && typeof event.pattern === "object"
          ? Object.entries(event.pattern)
              .map(([k, v]) => `${k}: ${String(v)}`)
              .join(", ")
          : undefined;
      normalized.push({
        id: baseId,
        scope,
        kind: "pattern",
        expression: event.condition || event.expression,
        patternSummary,
        result: Boolean(event.result ?? event.evaluated ?? event.taken),
        taken: Boolean(event.taken ?? event.result ?? event.evaluated),
        bindingName: event.binding?.name,
        bindingValue: event.binding?.value,
        timestamp: event.timestamp,
      });
      return;
    }
    if (isRuleGroupEvent(event)) {
      normalized.push({
        id: baseId,
        scope,
        kind: "rulegroup",
        rulegroup: event.rulegroup,
        ruleName: event.condition,
        expression: event.rulegroup
          ? event.condition
            ? `${event.rulegroup}.${event.condition}`
            : event.rulegroup
          : event.condition,
        result: Boolean(event.result ?? event.evaluated ?? event.taken),
        taken: Boolean(event.taken ?? event.result ?? event.evaluated),
        timestamp: event.timestamp,
      });
      return;
    }
    if (isConditionEvent(event)) {
      normalized.push({
        id: baseId,
        scope,
        kind: "simple",
        expression: event.condition || event.expression || event.message,
        macro: (event as any).macro,
        result: Boolean(event.result ?? event.evaluated ?? event.taken),
        taken: Boolean(event.taken ?? event.result ?? event.evaluated),
        bindingName: event.binding?.name,
        bindingValue: event.binding?.value,
        timestamp: event.timestamp,
      });
    }
  });

  // keep chronological order based on timestamp or input order
  return normalized.sort((a, b) => {
    if (a.timestamp && b.timestamp) {
      return a.timestamp.localeCompare(b.timestamp);
    }
    return 0;
  });
};

export const countConditions = (events: TraceEvent[] | undefined | null): number => {
  return normalizeConditions(events).length;
};

export const isFlowGotoEvent = (event: TraceEvent): event is FlowGotoEvent => {
  return (event.event || event.kind) === "flow.goto";
};
