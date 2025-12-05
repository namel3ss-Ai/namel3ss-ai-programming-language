import { describe, it, expect } from "vitest";
import { normalizeConditions } from "../trace/conditions";
import type { TraceEvent } from "../api/types";

describe("normalizeConditions", () => {
  it("normalizes simple condition events", () => {
    const events: TraceEvent[] = [
      { id: "1", event: "condition.eval", condition: "x > 1", result: true, scope: "flow" },
    ];
    const normalized = normalizeConditions(events);
    expect(normalized).toHaveLength(1);
    expect(normalized[0].expression).toBe("x > 1");
    expect(normalized[0].taken).toBe(true);
    expect(normalized[0].scope).toBe("flow");
  });

  it("normalizes pattern events with summary", () => {
    const events: TraceEvent[] = [
      { id: "p1", event: "condition.pattern.eval", pattern: { category: "billing" }, result: false, scope: "agent" },
    ];
    const normalized = normalizeConditions(events);
    expect(normalized[0].kind).toBe("pattern");
    expect(normalized[0].patternSummary).toContain("category");
    expect(normalized[0].taken).toBe(false);
  });

  it("normalizes rulegroup events", () => {
    const events: TraceEvent[] = [
      {
        id: "rg1",
        event: "condition.rulegroup.eval",
        rulegroup: "vip_rules",
        results: { age_ok: true, value_ok: false },
        result: false,
      },
    ];
    const normalized = normalizeConditions(events);
    expect(normalized[0].kind).toBe("rulegroup");
    expect(normalized[0].rulegroup).toBe("vip_rules");
    expect(normalized[0].taken).toBe(false);
  });
});
