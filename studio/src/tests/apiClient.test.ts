import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiClient } from "../api/client";

const originalFetch = global.fetch;

describe("ApiClient", () => {
beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ pages: [] }),
  }) as any;
});

  it("sends api key header", async () => {
    await ApiClient.fetchPages("code");
    expect(global.fetch).toHaveBeenCalled();
    const args = (global.fetch as any).mock.calls[0];
    const init = args[1];
    expect(init.headers["X-API-Key"]).toBeDefined();
  });
});

afterEach(() => {
  global.fetch = originalFetch;
});
