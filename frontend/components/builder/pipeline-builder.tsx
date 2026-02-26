"use client";

import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import {
  Background,
  BackgroundVariant,
  ConnectionLineType,
  Controls,
  MarkerType,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  type NodeMouseHandler,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { createDagValidator } from "@/lib/builder/dag-validation";
import { getLayoutedElements } from "@/lib/builder/layout";
import { usePipelineStore } from "@/lib/builder/store";
import { PIPELINE_NODE_DEFAULTS, type AppNode, type PipelineNodeType } from "@/lib/builder/types";
import { edgeTypes } from "./edges";
import { NodeConfigPanel } from "./node-config-panel";
import { NodePalette } from "./node-palette";
import { nodeTypes } from "./nodes";
import { RunToolbar } from "./run-toolbar";

let nodeIdCounter = 0;

function getNodeId() {
  return `node-${Date.now()}-${nodeIdCounter++}`;
}

const defaultEdgeOptions = {
  type: "pipeline" as const,
  animated: false,
  markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
};

function miniMapNodeColor(node: AppNode): string {
  switch (node.type) {
    case "ingest":
      return "#6366f1";
    case "bm25_search":
      return "#0ea5e9";
    case "read_document":
      return "#22d3ee";
    case "parallel_search":
      return "#14b8a6";
    case "agent":
      return "#10b981";
    case "output":
      return "#f59e0b";
    default:
      return "#57534e";
  }
}

function PipelineBuilderInner() {
  const nodes = usePipelineStore((s) => s.nodes);
  const edges = usePipelineStore((s) => s.edges);
  const onNodesChange = usePipelineStore((s) => s.onNodesChange);
  const onEdgesChange = usePipelineStore((s) => s.onEdgesChange);
  const onConnect = usePipelineStore((s) => s.onConnect);
  const addNode = usePipelineStore((s) => s.addNode);
  const setSelectedNodeId = usePipelineStore((s) => s.setSelectedNodeId);
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId);
  const undo = usePipelineStore((s) => s.undo);
  const redo = usePipelineStore((s) => s.redo);
  const toJSON = usePipelineStore((s) => s.toJSON);
  const fromJSON = usePipelineStore((s) => s.fromJSON);

  const [showPaletteSheet, setShowPaletteSheet] = useState(false);
  const [showConfigSheet, setShowConfigSheet] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  const { fitView, getEdges, getNodes, screenToFlowPosition } = useReactFlow();
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 1023px)");
    const sync = () => setIsMobile(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  const addNodeAt = useCallback(
    (nodeType: PipelineNodeType, x?: number, y?: number) => {
      const defaults = PIPELINE_NODE_DEFAULTS[nodeType];
      const position =
        typeof x === "number" && typeof y === "number"
          ? screenToFlowPosition({ x, y })
          : screenToFlowPosition({
              x: window.innerWidth / 2,
              y: window.innerHeight / 2,
            });
      const newNode: AppNode = {
        id: getNodeId(),
        type: nodeType,
        position,
        data: defaults(),
      } as AppNode;
      addNode(newNode);
    },
    [addNode, screenToFlowPosition],
  );

  const onNodeClick: NodeMouseHandler = useCallback(
    (_e, node) => {
      setSelectedNodeId(node.id);
      if (isMobile) setShowConfigSheet(true);
    },
    [isMobile, setSelectedNodeId],
  );

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, [setSelectedNodeId]);

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();
      const nodeType = event.dataTransfer.getData("application/reactflow");
      if (!nodeType || !(nodeType in PIPELINE_NODE_DEFAULTS)) return;
      addNodeAt(
        nodeType as PipelineNodeType,
        event.clientX,
        event.clientY,
      );
    },
    [addNodeAt],
  );

  const isValidConnection = useCallback(
    (connection: Parameters<ReturnType<typeof createDagValidator>>[0]) =>
      createDagValidator(nodes, edges)(connection),
    [nodes, edges],
  );

  const onLayout = useCallback(
    (direction: "TB" | "LR") => {
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements<AppNode>(
        getNodes() as AppNode[],
        getEdges(),
        direction,
      );
      fromJSON({ nodes: layoutedNodes, edges: layoutedEdges });
      window.requestAnimationFrame(() => fitView({ duration: 280 }));
    },
    [fitView, fromJSON, getEdges, getNodes],
  );

  const onSave = useCallback(() => {
    localStorage.setItem("synextra-pipeline-v2", JSON.stringify(toJSON()));
  }, [toJSON]);

  const onRestore = useCallback(() => {
    const raw = localStorage.getItem("synextra-pipeline-v2");
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed?.nodes && parsed?.edges) {
      fromJSON(parsed);
      window.requestAnimationFrame(() => fitView({ duration: 280 }));
    }
  }, [fitView, fromJSON]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <RunToolbar
        onOpenPalette={() => setShowPaletteSheet(true)}
        onOpenConfig={() => setShowConfigSheet(true)}
        hasSelection={Boolean(selectedNodeId)}
      />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[14rem_minmax(0,1fr)_18rem]">
        <div className="hidden min-h-0 lg:block">
          <NodePalette onAddNode={(type) => addNodeAt(type)} />
        </div>

        <div ref={wrapperRef} className="relative min-h-0 rounded-lg border border-stone-800">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onDrop={onDrop}
            onDragOver={onDragOver}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            defaultEdgeOptions={defaultEdgeOptions}
            connectionLineType={ConnectionLineType.SmoothStep}
            isValidConnection={isValidConnection}
            connectOnClick
            connectionRadius={24}
            fitView
            colorMode="dark"
            deleteKeyCode={["Backspace", "Delete"]}
            snapToGrid
            snapGrid={[16, 16]}
            panOnScroll
            preventScrolling={false}
            zoomOnDoubleClick={!isMobile}
            selectionOnDrag={!isMobile}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={16}
              size={1}
              color="#333"
            />
            <Controls showInteractive={false} position="bottom-left" />
            {!isMobile && (
              <MiniMap
                nodeColor={miniMapNodeColor}
                maskColor="rgba(0, 0, 0, 0.7)"
                bgColor="#0a0a0a"
                position="bottom-right"
              />
            )}

            <Panel position="top-right">
              <div className="flex flex-wrap justify-end gap-1.5">
                <PanelButton onClick={() => onLayout("LR")}>Layout &rarr;</PanelButton>
                <PanelButton onClick={() => onLayout("TB")}>Layout &darr;</PanelButton>
                <PanelButton onClick={undo}>Undo</PanelButton>
                <PanelButton onClick={redo}>Redo</PanelButton>
                <PanelButton onClick={onSave}>Save</PanelButton>
                <PanelButton onClick={onRestore}>Restore</PanelButton>
              </div>
            </Panel>
          </ReactFlow>
        </div>

        <div className="hidden min-h-0 lg:block">
          {selectedNodeId ? (
            <NodeConfigPanel onClose={() => setSelectedNodeId(null)} />
          ) : (
            <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-stone-700 text-xs text-stone-500">
              Select a node to configure it
            </div>
          )}
        </div>
      </div>

      {showPaletteSheet && (
        <MobileSheet onClose={() => setShowPaletteSheet(false)} title="Pipeline Nodes">
          <NodePalette
            onAddNode={(type) => {
              addNodeAt(type);
              setShowPaletteSheet(false);
            }}
          />
        </MobileSheet>
      )}

      {showConfigSheet && selectedNodeId && (
        <MobileSheet onClose={() => setShowConfigSheet(false)} title="Node Config">
          <NodeConfigPanel onClose={() => setShowConfigSheet(false)} />
        </MobileSheet>
      )}
    </div>
  );
}

function PanelButton({
  onClick,
  children,
}: {
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="rounded-md border border-stone-700 bg-stone-900 px-2.5 py-1 text-xs text-stone-300 hover:bg-stone-800"
    >
      {children}
    </button>
  );
}

function MobileSheet({
  onClose,
  title,
  children,
}: {
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/75 p-3 lg:hidden">
      <div className="flex max-h-[80vh] w-full flex-col overflow-hidden rounded-xl border border-stone-800 bg-stone-950">
        <div className="flex items-center justify-between border-b border-stone-800 px-3 py-2">
          <h3 className="text-sm font-semibold text-stone-200">{title}</h3>
          <button onClick={onClose} className="text-sm text-stone-400 hover:text-stone-200">
            Close
          </button>
        </div>
        <div className="min-h-0 overflow-auto p-3">{children}</div>
      </div>
    </div>
  );
}

export function PipelineBuilder() {
  return (
    <ReactFlowProvider>
      <PipelineBuilderInner />
    </ReactFlowProvider>
  );
}
