import { beforeEach, describe, expect, it } from "vitest";

import { clearAllNodeFiles, getNodeFile, setNodeFile } from "./file-store";
import { usePipelineStore } from "./store";
import type { AppNode } from "./types";

function makeIngestNode(id: string): AppNode {
  return {
    id,
    type: "ingest",
    position: { x: 0, y: 0 },
    data: { label: "Ingest", status: "idle" },
  } as AppNode;
}

describe("pipeline store file lifecycle", () => {
  beforeEach(() => {
    clearAllNodeFiles();
    usePipelineStore.setState({
      nodes: [],
      edges: [],
      selectedNodeId: null,
      history: [],
      historyIndex: -1,
    });
  });

  it("clears stored file when nodes are removed via removeNodes", () => {
    const store = usePipelineStore.getState();
    store.addNode(makeIngestNode("ing-1"));
    setNodeFile("ing-1", new File(["hello"], "notes.md", { type: "text/markdown" }));

    expect(getNodeFile("ing-1")).toBeInstanceOf(File);
    store.removeNodes(["ing-1"]);
    expect(getNodeFile("ing-1")).toBeUndefined();
  });

  it("clears all stored files on fromJSON restore", () => {
    setNodeFile("ing-1", new File(["hello"], "notes.md", { type: "text/markdown" }));
    expect(getNodeFile("ing-1")).toBeInstanceOf(File);

    usePipelineStore.getState().fromJSON({
      nodes: [makeIngestNode("ing-2")],
      edges: [],
    });

    expect(getNodeFile("ing-1")).toBeUndefined();
  });
});
