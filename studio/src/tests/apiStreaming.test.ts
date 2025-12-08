import { describe, it, expect, vi, afterEach } from "vitest";
import { runFlowStreaming } from "../api/client";

describe("runFlowStreaming", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("parses newline-delimited events", async () => {
    const events: any[] = [];
    const chunks = [
      `{"event":"ai_chunk","step":"answer","delta":"Hel"}\n{"event":"ai_chunk","step":"answer","delta":"lo"}\n`,
      `{"event":"ai_done","step":"answer","full":"Hello"}\n{"event":"flow_done","success":true}\n`,
    ];
    const mockReader = {
      read: vi
        .fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(chunks[0]) })
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(chunks[1]) })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    };
    const mockResponse = {
      ok: true,
      body: {
        getReader: () => mockReader,
      },
    };
    vi.spyOn(global, "fetch" as any).mockResolvedValue(mockResponse as any);
    await runFlowStreaming("chat_turn", { question: "Hi" }, (evt) => events.push(evt));
    expect(events).toHaveLength(4);
    expect(events[0].delta).toBe("Hel");
    expect(events[2].full).toBe("Hello");
  });
});
