import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AiMessageBubble } from "@/components/ai-elements/message-bubble";

describe("AiMessageBubble", () => {
  it("renders text content for a user message", () => {
    render(<AiMessageBubble role="user" text="Hello" />);

    expect(screen.getByText("user")).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("applies assistant styling variant", () => {
    render(<AiMessageBubble role="assistant" text="World" />);

    const bubble = screen.getByText("assistant").parentElement;
    expect(bubble?.className).toContain("bg-black");
  });

  it("renders markdown for assistant responses", () => {
    render(<AiMessageBubble role="assistant" text={"# Heading\n\nSome text"} />);

    expect(screen.getByRole("heading", { name: "Heading" })).toBeInTheDocument();
  });

  it("handles unknown roles without crashing", () => {
    render(<AiMessageBubble role="tool" text="Tool output" />);

    expect(screen.getByText("tool")).toBeInTheDocument();
  });
});
