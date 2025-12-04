import { describe, it, expect } from "vitest";
import { applyLastTrace, applyRunResponse, createInitialRunState } from "../ide/runState";

describe("runState model", () => {
  it("initial run state has null response and trace", () => {
    const state = createInitialRunState();
    expect(state.lastRunResponse).toBeNull();
    expect(state.lastTrace).toBeNull();
  });

  it("applyRunResponse stores the run response", () => {
    const state = createInitialRunState();
    const run = applyRunResponse(state, { status: "ok", message: "done" });
    expect(run.lastRunResponse?.status).toBe("ok");
    expect(run.lastRunResponse?.message).toBe("done");
  });

  it("applyLastTrace stores the last trace", () => {
    const state = createInitialRunState();
    const trace = applyLastTrace(state, { id: "trace-1", started_at: "now" } as any);
    expect(trace.lastTrace?.id).toBe("trace-1");
  });
});
