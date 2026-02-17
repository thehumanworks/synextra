import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useChat } from "@ai-sdk/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IntegrationDemo } from "@/components/integration-demo";

vi.mock("@ai-sdk/react", () => ({
  useChat: vi.fn(),
}));

type UseChatState = {
  messages: Array<{ id: string; role: string; parts: Array<{ type: string; text?: string }> }>;
  sendMessage: ReturnType<typeof vi.fn>;
  status: "ready" | "submitted" | "streaming" | "error";
  error: Error | undefined;
};

const mockUseChat = vi.mocked(useChat);

function buildUseChatState(overrides: Partial<UseChatState> = {}): UseChatState {
  return {
    messages: [],
    sendMessage: vi.fn().mockResolvedValue(undefined),
    status: "ready",
    error: undefined,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("IntegrationDemo", () => {
  it("renders the empty-state message when there are no chat messages", () => {
    mockUseChat.mockReturnValue(buildUseChatState() as never);

    render(<IntegrationDemo />);

    expect(screen.getByText("No chat messages yet.")).toBeInTheDocument();
    expect(screen.getByText("Ready. Type and send a prompt.")).toBeInTheDocument();
  });

  it("shows an error label and message when hook status is error", () => {
    mockUseChat.mockReturnValue(
      buildUseChatState({
        status: "error",
        error: new Error("route failure"),
      }) as never,
    );

    render(<IntegrationDemo />);

    expect(screen.getByText("The request failed. Check /api/chat.")).toBeInTheDocument();
    expect(screen.getByText("route failure")).toBeInTheDocument();
  });

  it("sends trimmed prompts and clears the input", async () => {
    const user = userEvent.setup();
    const sendMessage = vi.fn().mockResolvedValue(undefined);
    mockUseChat.mockReturnValue(buildUseChatState({ sendMessage }) as never);

    render(<IntegrationDemo />);

    const input = screen.getByPlaceholderText("Ask something about this scaffold...");
    await user.type(input, "  hello scaffold  ");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(sendMessage).toHaveBeenCalledWith({ text: "hello scaffold" });
    expect(input).toHaveValue("");
  });

  it("does not send blank prompts", async () => {
    const user = userEvent.setup();
    const sendMessage = vi.fn().mockResolvedValue(undefined);
    mockUseChat.mockReturnValue(buildUseChatState({ sendMessage }) as never);

    render(<IntegrationDemo />);

    const input = screen.getByPlaceholderText("Ask something about this scaffold...");
    await user.type(input, "   ");
    await user.keyboard("{Enter}");

    expect(sendMessage).not.toHaveBeenCalled();
  });
});
