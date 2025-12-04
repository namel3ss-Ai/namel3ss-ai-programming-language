import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiClient } from "../api/client";
import type { FmtPreviewResponse, PluginMetadata } from "../api/types";

const originalFetch = global.fetch;

describe("ApiClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn() as any;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("sends api key header", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ pages: [] }),
    });
    await ApiClient.fetchPages("code");
    expect(global.fetch).toHaveBeenCalled();
    const args = (global.fetch as any).mock.calls[0];
    const init = args[1];
    expect(init.headers["X-API-Key"]).toBeDefined();
  });

  it("postFmtPreview sends source and returns formatted result", async () => {
    const mockResponse: FmtPreviewResponse = { formatted: "formatted-content", changes_made: true };
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });
    const result = await ApiClient.postFmtPreview("unformatted-content");
    expect(result).toEqual(mockResponse);
    const args = (global.fetch as any).mock.calls[0];
    expect(args[0]).toContain("/api/fmt/preview");
    const body = JSON.parse(args[1].body);
    expect(body.source).toBe("unformatted-content");
  });

  it("fetchPlugins returns plugin metadata list", async () => {
    const mockPlugins: PluginMetadata[] = [
      { id: "example-plugin", name: "Example Plugin", version: "1.0.0", entrypoints: {}, tags: ["tools"] },
    ];
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ plugins: mockPlugins }),
    });
    const result = await ApiClient.fetchPlugins();
    expect(Array.isArray(result)).toBe(true);
    expect(result[0].id).toBe("example-plugin");
    expect(result[0].tags).toContain("tools");
  });
});
