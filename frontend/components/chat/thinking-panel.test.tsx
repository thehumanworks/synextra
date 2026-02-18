import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { StreamEvent } from "@/lib/chat/stream-metadata";
import { ThinkingPanel } from "./thinking-panel";

const SEARCH_EVENT: StreamEvent = {
  event: "search",
  tool: "bm25_search",
  query: "what is entropy",
  timestamp: "2024-01-01T00:00:00Z",
};

const READ_PAGE_EVENT: StreamEvent = {
  event: "search",
  tool: "read_document",
  page: 3,
  timestamp: "2024-01-01T00:00:01Z",
};

const REVIEW_APPROVED_EVENT: StreamEvent = {
  event: "review",
  iteration: 1,
  verdict: "approved",
  timestamp: "2024-01-01T00:00:02Z",
};

const REVIEW_REJECTED_EVENT: StreamEvent = {
  event: "review",
  iteration: 1,
  verdict: "rejected",
  feedback: "Missing key detail",
  timestamp: "2024-01-01T00:00:03Z",
};

const REASONING_EVENT: StreamEvent = {
  event: "reasoning",
  content: "Thinking through the problem…",
  timestamp: "2024-01-01T00:00:04Z",
};

describe("ThinkingPanel", () => {
  it("renders nothing when events array is empty", () => {
    const { container } = render(<ThinkingPanel events={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the panel when events are present", () => {
    render(<ThinkingPanel events={[SEARCH_EVENT]} />);
    expect(screen.getByTestId("thinking-panel")).toBeInTheDocument();
  });

  it("renders search events with query text", () => {
    render(<ThinkingPanel events={[SEARCH_EVENT]} />);
    expect(screen.getByText(/Search: what is entropy/i)).toBeInTheDocument();
  });

  it("renders read_document event with page number", () => {
    render(<ThinkingPanel events={[READ_PAGE_EVENT]} />);
    expect(screen.getByText(/Read page 3/i)).toBeInTheDocument();
  });

  it("renders review approved event", () => {
    render(<ThinkingPanel events={[REVIEW_APPROVED_EVENT]} />);
    expect(screen.getByText(/Review passed/i)).toBeInTheDocument();
  });

  it("renders review rejected event with feedback", () => {
    render(<ThinkingPanel events={[REVIEW_REJECTED_EVENT]} />);
    expect(screen.getByText(/Review rejected: Missing key detail/i)).toBeInTheDocument();
  });

  it("renders reasoning event", () => {
    render(<ThinkingPanel events={[REASONING_EVENT]} />);
    expect(screen.getByText(/Thinking through the problem/i)).toBeInTheDocument();
  });

  it("renders multiple events in an ordered list", () => {
    render(
      <ThinkingPanel
        events={[SEARCH_EVENT, REVIEW_APPROVED_EVENT]}
      />,
    );
    const list = screen.getByRole("list", { name: /retrieval steps/i });
    const items = list.querySelectorAll("li");
    expect(items).toHaveLength(2);
  });

  it("shows step count in the toggle button", () => {
    render(<ThinkingPanel events={[SEARCH_EVENT, REVIEW_APPROVED_EVENT]} />);
    expect(screen.getByRole("button", { name: /2 steps/i })).toBeInTheDocument();
  });

  it("shows singular 'step' for a single event", () => {
    render(<ThinkingPanel events={[SEARCH_EVENT]} />);
    expect(screen.getByRole("button", { name: /1 step/i })).toBeInTheDocument();
  });

  it("shows 'Retrieving…' label while streaming", () => {
    render(<ThinkingPanel events={[SEARCH_EVENT]} isStreaming />);
    expect(screen.getByRole("button", { name: /retrieving/i })).toBeInTheDocument();
  });

  it("is expanded by default and shows event items", () => {
    render(<ThinkingPanel events={[SEARCH_EVENT]} />);
    const toggle = screen.getByRole("button");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/Search: what is entropy/i)).toBeInTheDocument();
  });

  it("collapses when toggle button is clicked", async () => {
    const user = userEvent.setup();
    render(<ThinkingPanel events={[SEARCH_EVENT]} />);

    const toggle = screen.getByRole("button");
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    await user.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("re-expands when toggle is clicked again after collapsing", async () => {
    const user = userEvent.setup();
    render(<ThinkingPanel events={[SEARCH_EVENT]} />);

    const toggle = screen.getByRole("button");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });
});
