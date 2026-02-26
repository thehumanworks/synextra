import { create } from "zustand";
import {
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
} from "@xyflow/react";
import type { AppNode, AppEdge, NodeStatus } from "./types";
import { clearAllNodeFiles, clearNodeFile } from "./file-store";

type PipelineStore = {
  // --- Flow state ---
  nodes: AppNode[];
  edges: AppEdge[];
  onNodesChange: OnNodesChange<AppNode>;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;

  // --- Node mutations ---
  addNode: (node: AppNode) => void;
  updateNodeData: (id: string, patch: Record<string, unknown>) => void;
  setNodeStatus: (id: string, status: NodeStatus, error?: string) => void;
  removeNodes: (ids: string[]) => void;
  removeEdges: (ids: string[]) => void;

  // --- Selection ---
  selectedNodeId: string | null;
  setSelectedNodeId: (id: string | null) => void;

  // --- Undo/Redo ---
  history: { nodes: AppNode[]; edges: AppEdge[] }[];
  historyIndex: number;
  pushHistory: () => void;
  undo: () => void;
  redo: () => void;

  // --- Serialization ---
  toJSON: () => { nodes: AppNode[]; edges: AppEdge[] };
  fromJSON: (data: { nodes: AppNode[]; edges: AppEdge[] }) => void;
};

const MAX_HISTORY = 50;

export const usePipelineStore = create<PipelineStore>((set, get) => ({
  nodes: [],
  edges: [],

  onNodesChange: (changes) => {
    for (const change of changes) {
      if (change.type === "remove") {
        clearNodeFile(change.id);
      }
    }
    set({ nodes: applyNodeChanges(changes, get().nodes) as AppNode[] });
  },

  onEdgesChange: (changes) =>
    set({ edges: applyEdgeChanges(changes, get().edges) }),

  onConnect: (conn) => {
    get().pushHistory();
    set({ edges: addEdge(conn, get().edges) });
  },

  addNode: (node) => {
    get().pushHistory();
    set({ nodes: [...get().nodes, node] });
  },

  updateNodeData: (id, patch) =>
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? ({ ...n, data: { ...n.data, ...patch } } as AppNode) : n,
      ),
    }),

  setNodeStatus: (id, status, error) =>
    set({
      nodes: get().nodes.map((n) =>
        n.id === id
          ? ({
              ...n,
              data: {
                ...n.data,
                status,
                ...(error !== undefined ? { error } : {}),
              },
            } as AppNode)
          : n,
      ),
    }),

  removeNodes: (ids) => {
    get().pushHistory();
    const idSet = new Set(ids);
    for (const id of ids) {
      clearNodeFile(id);
    }
    set({
      nodes: get().nodes.filter((n) => !idSet.has(n.id)),
      edges: get().edges.filter(
        (e) => !idSet.has(e.source) && !idSet.has(e.target),
      ),
      selectedNodeId:
        get().selectedNodeId && idSet.has(get().selectedNodeId!)
          ? null
          : get().selectedNodeId,
    });
  },

  removeEdges: (ids) => {
    get().pushHistory();
    const idSet = new Set(ids);
    set({ edges: get().edges.filter((e) => !idSet.has(e.id)) });
  },

  // --- Selection ---
  selectedNodeId: null,
  setSelectedNodeId: (id) => set({ selectedNodeId: id }),

  // --- Undo/Redo ---
  history: [],
  historyIndex: -1,

  pushHistory: () => {
    const { nodes, edges, history, historyIndex } = get();
    const trimmed = history.slice(0, historyIndex + 1);
    const next = [
      ...trimmed,
      { nodes: structuredClone(nodes), edges: structuredClone(edges) },
    ];
    if (next.length > MAX_HISTORY) next.shift();
    set({ history: next, historyIndex: next.length - 1 });
  },

  undo: () => {
    const { history, historyIndex, nodes, edges } = get();
    if (historyIndex < 0) return;
    const snapshot = history[historyIndex];
    const updated = [...history];
    updated[historyIndex] = {
      nodes: structuredClone(nodes),
      edges: structuredClone(edges),
    };
    set({
      nodes: snapshot.nodes,
      edges: snapshot.edges,
      history: updated,
      historyIndex: historyIndex - 1,
    });
  },

  redo: () => {
    const { history, historyIndex } = get();
    if (historyIndex >= history.length - 1) return;
    const next = historyIndex + 1;
    const snapshot = history[next];
    set({
      nodes: snapshot.nodes,
      edges: snapshot.edges,
      historyIndex: next,
    });
  },

  // --- Serialization ---
  toJSON: () => {
    const { nodes, edges } = get();
    return { nodes, edges };
  },

  fromJSON: (data) => {
    get().pushHistory();
    clearAllNodeFiles();
    set({ nodes: data.nodes, edges: data.edges, selectedNodeId: null });
  },
}));
