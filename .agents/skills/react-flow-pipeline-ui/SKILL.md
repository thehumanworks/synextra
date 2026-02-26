---
name: react-flow-pipeline-ui
description: Build flow-based UIs with React Flow (@xyflow/react v12+) for node-based editors, workflow builders, pipeline visualizers, and computing flows. Use when creating drag-and-drop node editors, DAG pipeline UIs, visual workflow execution monitors, or any interactive graph-based interface. Covers custom nodes/edges, theming (dark mode, CSS variables), state management (Zustand), layout algorithms (dagre, ELK), performance optimization, keyboard shortcuts, context menus, undo/redo, save/restore, accessibility, testing, and Next.js SSR. Grounded in synextra SDK/backend capabilities for document processing pipelines.
---

# React Flow Pipeline UI

Build flow-based UIs with [React Flow](https://reactflow.dev) (`@xyflow/react` v12+). This skill covers everything from basic setup to production-grade pipeline builders with real-time execution status, theming, and performance optimization.

## Quick Start

```bash
npm install @xyflow/react
```

```tsx
import { useCallback } from 'react';
import {
  ReactFlow, useNodesState, useEdgesState, addEdge,
  Background, Controls, ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

const initialNodes = [
  { id: '1', type: 'input', position: { x: 0, y: 0 }, data: { label: 'Input' } },
  { id: '2', position: { x: 250, y: 0 }, data: { label: 'Process' } },
];
const initialEdges = [{ id: 'e1-2', source: '1', target: '2' }];

// CRITICAL: Define nodeTypes at module scope. Inline objects cause remount every render.
const nodeTypes = {};

function Flow() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div style={{ height: '100%', width: '100%' }}>
      <ReactFlow
        nodes={nodes} edges={edges}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        onConnect={onConnect} nodeTypes={nodeTypes} fitView
        colorMode="dark"
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}

// useReactFlow() requires ReactFlowProvider wrapping the calling component
export default () => (
  <ReactFlowProvider><Flow /></ReactFlowProvider>
);
```

## Core Concepts

| Concept | Key Points |
|---------|------------|
| **Nodes** | `{ id, position: {x,y}, data, type? }`. Custom types via `nodeTypes` map. |
| **Edges** | `{ id, source, target, sourceHandle?, targetHandle?, type? }`. Custom types via `edgeTypes`. |
| **Handles** | `<Handle type="source\|target" position={Position.Left\|Right\|Top\|Bottom} id?="name" />` |
| **nodeTypes / edgeTypes** | **Must be defined at module scope** — never inside a component. React Flow error002. |
| **ReactFlowProvider** | Required wrapper when using `useReactFlow()`. `<ReactFlow>` itself is NOT a provider. |

### TypeScript: Typed Nodes

```ts
import type { Node, NodeProps, BuiltInNode } from '@xyflow/react';

type ChunkNodeData = { tokenTarget: number; status: 'idle' | 'running' | 'done' | 'error' };
export type ChunkNode = Node<ChunkNodeData, 'chunk'>;
export type AppNode = BuiltInNode | ChunkNode;

// In the component — data is fully typed
function ChunkNodeComponent({ id, data }: NodeProps<ChunkNode>) {
  return <div className="nodrag">Token target: {data.tokenTarget}</div>;
}
```

`BuiltInNode` covers `input`, `output`, `default`, and `group` built-in types.

## Custom Nodes

```tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

const PipelineNode = memo(function PipelineNode({ data }: NodeProps) {
  return (
    <div className="pipeline-node">
      <Handle type="target" position={Position.Left} />
      <div className="nodrag">{data.label}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
});

const nodeTypes = { pipeline: PipelineNode }; // module scope
```

Use `nodrag` class on interactive elements (inputs, buttons, selects) to prevent triggering node drag. Use `nokey` on text inputs to prevent keyboard shortcuts from firing while typing.

### Multiple Handles

```tsx
<Handle type="source" position={Position.Right} id="a" />
<Handle type="source" position={Position.Bottom} id="b" />

// Edge connecting to a specific handle:
{ id: 'e1', source: 'n1', sourceHandle: 'a', target: 'n2' }
```

### Node Configuration Panel (click-to-configure)

```tsx
const [selectedNode, setSelectedNode] = useState<AppNode | null>(null);
const onNodeClick: NodeMouseHandler = useCallback((_e, node) => setSelectedNode(node), []);
const onPaneClick = useCallback(() => setSelectedNode(null), []);

// Write back:
const { updateNodeData } = useReactFlow();
updateNodeData(node.id, { tokenTarget: 512 }); // shallow-merges into node.data
```

### NodeToolbar

```tsx
import { NodeToolbar, Position } from '@xyflow/react';

function MyNode({ data }) {
  return (
    <>
      <NodeToolbar position={Position.Top} offset={10} align="center">
        <button>delete</button>
        <button>copy</button>
      </NodeToolbar>
      <div>{data.label}</div>
    </>
  );
}
```

Toolbar shows when node is selected. Override with `isVisible={true}`.

### NodeResizer

```tsx
import { NodeResizer } from '@xyflow/react';

function ResizableNode({ data, selected }) {
  return (
    <>
      <NodeResizer isVisible={selected} minWidth={100} minHeight={30} />
      <Handle type="target" position={Position.Left} />
      <div>{data.label}</div>
      <Handle type="source" position={Position.Right} />
    </>
  );
}
```

## Custom Edges

```tsx
import { BaseEdge, getSmoothStepPath, EdgeLabelRenderer, useReactFlow, type EdgeProps } from '@xyflow/react';

function DeleteButtonEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition }: EdgeProps) {
  const { deleteElements } = useReactFlow();
  const [path, labelX, labelY] = getSmoothStepPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });

  return (
    <>
      <BaseEdge id={id} path={path} />
      <EdgeLabelRenderer>
        <button
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className="nodrag nopan"
          onClick={() => deleteElements({ edges: [{ id }] })}
        >
          ×
        </button>
      </EdgeLabelRenderer>
    </>
  );
}

const edgeTypes = { deletable: DeleteButtonEdge }; // module scope
```

Path utils: `getStraightPath`, `getSmoothStepPath`, `getSimpleBezierPath`, `getBezierPath`. All return `[path, labelX, labelY]`.

### Animated Edge (SVG animateMotion)

```tsx
function AnimatedEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition }: EdgeProps) {
  const [path] = getSmoothStepPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
  return (
    <>
      <BaseEdge id={id} path={path} />
      <circle r="4" fill="#0ea5e9">
        <animateMotion dur="1.5s" repeatCount="indefinite" path={path} />
      </circle>
    </>
  );
}
```

For 100+ edges prefer SVG `animateMotion` over CSS `stroke-dasharray` (`animated: true`).

### Edge Markers

```tsx
import { MarkerType } from '@xyflow/react';

const defaultEdgeOptions = {
  animated: true,
  type: 'smoothstep',
  markerEnd: { type: MarkerType.ArrowClosed, width: 20, height: 20 },
};
<ReactFlow defaultEdgeOptions={defaultEdgeOptions} />
```

## Drag-and-Drop

```tsx
// Sidebar: set type on drag start
const onDragStart = (event: DragEvent, nodeType: string) => {
  event.dataTransfer.setData('application/reactflow', nodeType);
  event.dataTransfer.effectAllowed = 'move';
};

// Flow: handle drop with screenToFlowPosition (replaced project() in v12)
const { screenToFlowPosition } = useReactFlow();
const onDrop = (event: DragEvent) => {
  event.preventDefault();
  const type = event.dataTransfer.getData('application/reactflow');
  const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
  addNode({ id: getId(), type, position, data: { label: `${type} node` } });
};

<ReactFlow onDrop={onDrop} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }} />
```

## Connection Validation & DAG Enforcement

```tsx
import { getOutgoers } from '@xyflow/react';

const isValidConnection = (connection) => {
  const target = nodes.find((n) => n.id === connection.target);
  if (!target) return true;
  const hasCycle = (node, visited = new Set()) => {
    if (visited.has(node.id)) return false;
    visited.add(node.id);
    for (const outgoer of getOutgoers(node, nodes, edges)) {
      if (outgoer.id === connection.source) return true;
      if (hasCycle(outgoer, visited)) return true;
    }
    return false;
  };
  return !hasCycle(target);
};

<ReactFlow isValidConnection={isValidConnection} />
```

## State Management (Zustand)

`useNodesState`/`useEdgesState` for prototyping. For production, use Zustand:

```ts
import { create } from 'zustand';
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react';

const useStore = create((set, get) => ({
  nodes: [],
  edges: [],
  onNodesChange: (changes) => set({ nodes: applyNodeChanges(changes, get().nodes) }),
  onEdgesChange: (changes) => set({ edges: applyEdgeChanges(changes, get().edges) }),
  onConnect: (conn) => set({ edges: addEdge(conn, get().edges) }),
  updateNodeData: (id, patch) =>
    set({ nodes: get().nodes.map((n) => n.id === id ? { ...n, data: { ...n.data, ...patch } } : n) }),
}));
```

**Undo/redo**: Use `zundo` middleware or a manual history stack with `structuredClone`.

## Progressive Disclosure

- **Theming, CSS variables, dark mode**: [theming.md](theming.md)
- **Performance optimization (1000+ nodes)**: [performance.md](performance.md)
- **Layout algorithms (dagre, ELK)**: [layout.md](layout.md)
- **API reference (all props, hooks, utils, enums)**: [reference.md](reference.md)
- **Full code examples (drag-and-drop, context menu, subflows, save/restore, computing flows, keyboard, testing)**: [examples.md](examples.md)
- **Synextra SDK/backend node mapping and streaming protocol**: [synextra-pipeline-context.md](synextra-pipeline-context.md)
