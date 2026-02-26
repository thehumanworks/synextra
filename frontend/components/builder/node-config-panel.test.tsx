import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AppNode } from "@/lib/builder/types";
import { usePipelineStore } from "@/lib/builder/store";
import { NodeConfigPanel } from "./node-config-panel";

function makeAgentNode(id: string, output: string): AppNode {
  return {
    id,
    type: "agent",
    position: { x: 0, y: 0 },
    data: {
      label: "Agent Node",
      status: "done",
      promptTemplate: "{query}",
      reasoningEffort: "medium",
      reviewEnabled: false,
      tools: ["bm25_search"],
      output,
    },
  } as AppNode;
}

describe("NodeConfigPanel agent output tools", () => {
  beforeEach(() => {
    if (typeof URL.createObjectURL !== "function") {
      Object.defineProperty(URL, "createObjectURL", {
        configurable: true,
        writable: true,
        value: () => "blob:fallback",
      });
    }
    if (typeof URL.revokeObjectURL !== "function") {
      Object.defineProperty(URL, "revokeObjectURL", {
        configurable: true,
        writable: true,
        value: () => {},
      });
    }

    usePipelineStore.setState({
      nodes: [],
      edges: [],
      selectedNodeId: null,
      history: [],
      historyIndex: -1,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("opens a full-output dialog for agent node results", async () => {
    const user = userEvent.setup();
    const output = "Line one.\nLine two.\nLine three.";
    const node = makeAgentNode("agent-1", output);

    usePipelineStore.setState({
      nodes: [node],
      selectedNodeId: node.id,
    });

    render(<NodeConfigPanel onClose={vi.fn()} />);

    expect(
      screen.queryByRole("dialog", { name: "Full Agent Output" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "View Full Output" }));

    expect(
      screen.getByRole("dialog", { name: "Full Agent Output" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("full-agent-output").textContent).toBe(output);
  });

  it("downloads full agent output to a text file", async () => {
    const user = userEvent.setup();
    const output = "Complete output payload.\nWith multiple lines.";
    const node = makeAgentNode("agent-2", output);

    const createObjectURL = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:agent-output");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const appendSpy = vi.spyOn(document.body, "appendChild");
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    usePipelineStore.setState({
      nodes: [node],
      selectedNodeId: node.id,
    });

    render(<NodeConfigPanel onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Save Output to File" }));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const [firstCall] = createObjectURL.mock.calls;
    expect(firstCall).toBeDefined();
    const [blob] = firstCall ?? [];
    expect(blob).toBeInstanceOf(Blob);
    if (!(blob instanceof Blob)) {
      throw new Error("Expected createObjectURL to be called with Blob.");
    }
    expect(blob.type).toBe("text/plain;charset=utf-8");
    expect(blob.size).toBe(output.length);

    const link = appendSpy.mock.calls
      .map((call) => call[0])
      .find((node) => node instanceof HTMLAnchorElement) as HTMLAnchorElement | undefined;

    expect(link).toBeDefined();
    expect(link?.download).toBe("agent-node-agent-2-output.txt");
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:agent-output");
  });

  it("shows modal save errors and still revokes blob URLs on save failure", async () => {
    const user = userEvent.setup();
    const output = "Output that should fail to save.";
    const node = makeAgentNode("agent-3", output);

    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:failure");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {
      throw new Error("download blocked");
    });

    usePipelineStore.setState({
      nodes: [node],
      selectedNodeId: node.id,
    });

    render(<NodeConfigPanel onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "View Full Output" }));
    const dialog = screen.getByRole("dialog", { name: "Full Agent Output" });
    await user.click(within(dialog).getByRole("button", { name: "Save Output to File" }));

    expect(within(dialog).getByText("download blocked")).toBeInTheDocument();
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:failure");
  });
});
