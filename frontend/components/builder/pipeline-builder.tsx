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
import { usePipelineRun } from "@/lib/builder/use-pipeline-run";
import { edgeTypes } from "./edges";
import { NodeConfigPanel } from "./node-config-panel";
import { NodePalette } from "./node-palette";
import { nodeTypes } from "./nodes";

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
    case "input":
      return "#8b5cf6";
    case "ingest":
      return "#6366f1";
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

  const { runState, error, play, pause, stop, dismissError } = usePipelineRun();

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

  // Auto-dismiss error toast after 5 seconds
  useEffect(() => {
    if (!error) return;
    const timer = setTimeout(dismissError, 5000);
    return () => clearTimeout(timer);
  }, [error, dismissError]);

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
    <div className="flex h-full min-h-0 flex-col">
      <div className="grid min-h-0 flex-1 overflow-hidden grid-cols-1 gap-3 lg:grid-cols-[14rem_minmax(0,1fr)_18rem]">
        <div className="hidden min-h-0 lg:block">
          <NodePalette onAddNode={(type) => addNodeAt(type)} />
        </div>

        <div ref={wrapperRef} className="relative h-full min-h-0 rounded-lg border border-stone-800">
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
            fitViewOptions={{ maxZoom: 0.8, padding: 0.3 }}
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
              <div className="flex flex-wrap items-center justify-end gap-1.5">
                {runState === "idle" && (
                  <RunPanelButton
                    onClick={() => void play()}
                    title="Run"
                    className="text-emerald-400 hover:bg-emerald-900/30"
                  >
                    &#9654;
                  </RunPanelButton>
                )}
                {runState === "running" && (
                  <>
                    <RunPanelButton
                      onClick={() => void pause()}
                      title="Pause"
                      className="text-amber-400 hover:bg-amber-900/30"
                    >
                      &#9208;
                    </RunPanelButton>
                    <RunPanelButton
                      onClick={stop}
                      title="Stop"
                      className="text-red-400 hover:bg-red-900/30"
                    >
                      &#9209;
                    </RunPanelButton>
                  </>
                )}
                {runState === "paused" && (
                  <>
                    <RunPanelButton
                      onClick={() => void play()}
                      title="Resume"
                      className="text-emerald-400 hover:bg-emerald-900/30"
                    >
                      &#9654;
                    </RunPanelButton>
                    <RunPanelButton
                      onClick={stop}
                      title="Stop"
                      className="text-red-400 hover:bg-red-900/30"
                    >
                      &#9209;
                    </RunPanelButton>
                  </>
                )}
                <div className="h-4 w-px bg-stone-700" />
                <PanelButton onClick={() => onLayout("LR")}>Layout &rarr;</PanelButton>
                <PanelButton onClick={() => onLayout("TB")}>Layout &darr;</PanelButton>
                <PanelButton onClick={undo}>Undo</PanelButton>
                <PanelButton onClick={redo}>Redo</PanelButton>
                <PanelButton onClick={onSave}>Save</PanelButton>
                <PanelButton onClick={onRestore}>Restore</PanelButton>
              </div>
            </Panel>
          </ReactFlow>

          {error && (
            <div className="absolute left-1/2 top-4 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg border border-red-800 bg-red-950/90 px-4 py-2 text-sm text-red-300 shadow-lg backdrop-blur">
              <p>{error}</p>
              <button
                onClick={dismissError}
                className="ml-1 text-red-500 hover:text-red-300"
              >
                &#x2715;
              </button>
            </div>
          )}
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

      {/* Mobile bottom bar */}
      <div className="fixed bottom-4 left-1/2 z-40 flex -translate-x-1/2 gap-2 rounded-lg border border-stone-800 bg-stone-950/90 p-2 backdrop-blur lg:hidden">
        <button
          onClick={() => setShowPaletteSheet(true)}
          className="rounded-md border border-stone-700 bg-stone-900 px-2.5 py-1 text-xs text-stone-300 hover:bg-stone-800"
        >
          Nodes
        </button>
        <button
          onClick={() => setShowConfigSheet(true)}
          disabled={!selectedNodeId}
          className="rounded-md border border-stone-700 bg-stone-900 px-2.5 py-1 text-xs text-stone-300 hover:bg-stone-800 disabled:opacity-50"
        >
          Config
        </button>
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

function RunPanelButton({
  onClick,
  title,
  className,
  children,
}: {
  onClick: () => void;
  title: string;
  className: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`rounded-md border border-stone-700 bg-stone-900 px-2 py-1 text-sm leading-none ${className}`}
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
