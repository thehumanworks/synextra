import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderAgentEvents } from "./agent-event-renderers";
import type { AgentEvent } from "@/lib/chat/structured-response";

describe("agent-event-renderers", () => {
  it("renders known and unknown event types", () => {
    const events = [
      { type: "verifier", detail: "x" },
      { type: "mystery", payload: 1 },
    ] satisfies AgentEvent[];

    render(
      <div>
        {renderAgentEvents(events)}
      </div>,
    );

    expect(screen.getByText(/^Verifier$/i)).toBeInTheDocument();
    expect(screen.getByText(/Agent event: mystery/i)).toBeInTheDocument();
  });
});
