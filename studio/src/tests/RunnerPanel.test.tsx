import React from "react";
import { render, screen, act } from "@testing-library/react";
import { vi } from "vitest";
import RunnerPanel from "../panels/RunnerPanel";
import { ApiClient, StreamEvent } from "../api/client";

describe("RunnerPanel state streaming", () => {
  it("updates live state when receiving state_change events", () => {
    let stored: ((evt: StreamEvent) => void) | null = null;
    const unsubscribe = vi.fn();
    const fakeClient = {
      ...ApiClient,
      runApp: vi.fn(),
      subscribeStateStream: vi.fn((cb: (evt: StreamEvent) => void) => {
        stored = cb;
        return unsubscribe;
      }),
    };
    render(<RunnerPanel code="flow" client={fakeClient} />);
    expect(fakeClient.subscribeStateStream).toHaveBeenCalled();
    const evt: StreamEvent = {
      event: "state_change",
      path: "counter",
      old_value: 1,
      new_value: 5,
    } as any;
    act(() => {
      stored && stored(evt);
    });
    expect(screen.getByText(/"counter": 5/)).toBeInTheDocument();
  });
});
