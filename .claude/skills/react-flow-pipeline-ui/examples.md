# React Flow Code Examples

## Context Menu (Right-Click on Node)

```tsx
import { useCallback, useRef, useState } from 'react';
import { ReactFlow, useNodesState, useEdgesState, addEdge, Background } from '@xyflow/react';

function Flow() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [menu, setMenu] = useState(null);
  const ref = useRef(null);

  const onNodeContextMenu = useCallback((event, node) => {
    event.preventDefault();
    const pane = ref.current.getBoundingClientRect();
    setMenu({
      id: node.id,
      top: event.clientY < pane.height - 200 && event.clientY,
      left: event.clientX < pane.width - 200 && event.clientX,
      right: event.clientX >= pane.width - 200 && pane.width - event.clientX,
      bottom: event.clientY >= pane.height - 200 && pane.height - event.clientY,
    });
  }, []);

  const onPaneClick = useCallback(() => setMenu(null), []);

  return (
    <ReactFlow
      ref={ref}
      nodes={nodes} edges={edges}
      onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
      onConnect={(params) => setEdges((eds) => addEdge(params, eds))}
      onPaneClick={onPaneClick}
      onNodeContextMenu={onNodeContextMenu}
      fitView
    >
      <Background />
      {menu && <ContextMenu onClick={onPaneClick} {...menu} />}
    </ReactFlow>
  );
}
```

Also available: `onPaneContextMenu`, `onEdgeContextMenu`, `onSelectionContextMenu`.

## Subflows / Group Nodes

Parent must come before children in the array. Child `position` is relative to parent.

```tsx
const nodes = [
  {
    id: 'group-1', type: 'group',
    data: { label: 'Retrieval Stage' },
    position: { x: 200, y: 100 },
    style: { width: 300, height: 200, backgroundColor: 'rgba(0,100,255,0.05)' },
  },
  {
    id: 'bm25', data: { label: 'BM25 Search' },
    position: { x: 20, y: 60 },    // relative to group-1
    parentId: 'group-1',            // v12 (was parentNode in v11)
    extent: 'parent',               // locked inside parent
  },
  {
    id: 'vector', data: { label: 'Vector Search' },
    position: { x: 160, y: 60 },
    parentId: 'group-1',
    expandParent: true,             // parent grows to fit child
  },
];
```

Set `defaultEdgeOptions={{ zIndex: 1 }}` for edges between group children to render above the group background.

## Save and Restore

```tsx
import { useReactFlow, ReactFlowProvider, Panel } from '@xyflow/react';

function Flow() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const { toObject, setViewport } = useReactFlow();

  const onSave = () => {
    const flow = toObject(); // { nodes, edges, viewport }
    localStorage.setItem('flow', JSON.stringify(flow));
  };

  const onRestore = () => {
    const flow = JSON.parse(localStorage.getItem('flow') ?? '{}');
    if (flow.nodes) {
      setNodes(flow.nodes);
      setEdges(flow.edges ?? []);
      if (flow.viewport) setViewport(flow.viewport);
    }
  };

  return (
    <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} fitView>
      <Panel position="top-right">
        <button onClick={onSave}>Save</button>
        <button onClick={onRestore}>Restore</button>
      </Panel>
    </ReactFlow>
  );
}

// Wrap with ReactFlowProvider
export default () => <ReactFlowProvider><Flow /></ReactFlowProvider>;
```

## Computing Flows (Data Between Nodes)

```tsx
// TextNode — writes data to the global node state
import { Handle, Position, useReactFlow } from '@xyflow/react';

function TextNode({ id, data }) {
  const { updateNodeData } = useReactFlow();
  return (
    <div>
      <input
        className="nodrag"
        value={data.text}
        onChange={(e) => updateNodeData(id, { text: e.target.value })}
      />
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

// UppercaseNode — reads connected node data reactively
import { useNodeConnections, useNodesData } from '@xyflow/react';

function UppercaseNode({ id }) {
  const { updateNodeData } = useReactFlow();
  const connections = useNodeConnections({ handleType: 'target' });
  const nodesData = useNodesData(connections.map((c) => c.source));

  useEffect(() => {
    const text = nodesData?.[0]?.data?.text ?? '';
    updateNodeData(id, { text: text.toUpperCase() });
  }, [nodesData]);

  return (
    <div>
      <Handle type="target" position={Position.Left} />
      <div>uppercase transform</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

// ResultNode — reads multiple connected sources
function ResultNode() {
  const connections = useNodeConnections({ handleType: 'target' });
  const nodesData = useNodesData(connections.map((c) => c.source));
  return (
    <div>
      <Handle type="target" position={Position.Left} />
      {nodesData.map(({ data }, i) => <div key={i}>{data.text}</div>)}
    </div>
  );
}
```

## Add Node on Edge Drop

```tsx
const connectingNodeId = useRef(null);

const onConnectStart = useCallback((_, { nodeId }) => {
  connectingNodeId.current = nodeId;
}, []);

const onConnectEnd = useCallback((event) => {
  if (!connectingNodeId.current) return;
  const targetIsPane = (event.target as Element)?.classList?.contains('react-flow__pane');
  if (targetIsPane && 'clientX' in event) {
    const id = getId();
    setNodes((nds) => nds.concat({
      id,
      position: screenToFlowPosition({ x: event.clientX, y: event.clientY }),
      data: { label: `Node ${id}` },
      origin: [0.5, 0.0],
    }));
    setEdges((eds) => eds.concat({ id, source: connectingNodeId.current, target: id }));
  }
}, [screenToFlowPosition]);

<ReactFlow onConnectStart={onConnectStart} onConnectEnd={onConnectEnd} />
```

## Edge Reconnection

```tsx
import { reconnectEdge } from '@xyflow/react';

const onReconnect = useCallback(
  (oldEdge, newConnection) => setEdges((els) => reconnectEdge(oldEdge, newConnection, els)),
  [setEdges],
);

<ReactFlow edgesReconnectable onReconnect={onReconnect} />
```

Edge-level control: `reconnectable: 'source' | 'target' | true | false`.

## Keyboard Shortcuts

```tsx
import { useKeyPress } from '@xyflow/react';

const spacePressed = useKeyPress('Space');
const cmdS = useKeyPress(['Meta+s', 'Control+s']);

// Disable built-in delete and handle manually
<ReactFlow deleteKeyCode={[]} />

// Custom key bindings
<ReactFlow
  deleteKeyCode={['AltLeft+KeyD', 'Backspace']}
  selectionKeyCode="a+s"
  multiSelectionKeyCode={['ShiftLeft', 'ShiftRight']}
  zoomActivationKeyCode="z"
/>
```

## Viewport Control

```tsx
const { zoomIn, zoomOut, fitView, setViewport, setCenter, getZoom } = useReactFlow();

await zoomIn({ duration: 800 });
await fitView({ padding: 0.2, duration: 300 });
await fitView({ nodes: [{ id: 'n1' }, { id: 'n2' }] });
await setViewport({ x: 0, y: 0, zoom: 1 }, { duration: 800 });
await setCenter(100, 200, { zoom: 1.5, duration: 500 });
```

Figma-like controls:

```tsx
<ReactFlow
  panOnScroll={true}              // scroll to pan
  selectionOnDrag={true}          // drag to select
  panOnDrag={[1, 2]}              // middle+right mouse to pan
  zoomActivationKeyCode="Meta"
/>
```

## Dynamic Handles

```tsx
import { useUpdateNodeInternals } from '@xyflow/react';

function DynamicNode({ id }) {
  const [handleCount, setHandleCount] = useState(1);
  const updateNodeInternals = useUpdateNodeInternals();

  const addHandle = () => {
    setHandleCount((c) => c + 1);
    updateNodeInternals([id]); // notify RF about handle changes
  };

  return (
    <div>
      <Handle type="target" position={Position.Left} />
      <button onClick={addHandle}>Add handle</button>
      {Array.from({ length: handleCount }, (_, i) => (
        <Handle key={i} type="source" position={Position.Right} id={`h-${i}`} style={{ top: 20 + i * 15 }} />
      ))}
    </div>
  );
}
```

## Custom Connection Line

```tsx
function ConnectionLine({ fromX, fromY, toX, toY }) {
  return (
    <>
      <path
        fill="none" stroke="#222" strokeWidth={1.5}
        d={`M${fromX},${fromY} C ${fromX} ${toY} ${fromX} ${toY} ${toX},${toY}`}
      />
      <circle cx={toX} cy={toY} fill="#fff" r={3} stroke="#222" strokeWidth={1.5} />
    </>
  );
}

<ReactFlow connectionLineComponent={ConnectionLine} />
```

## Floating Edges (Center-to-Center)

```tsx
import { useStore, getBezierPath, type EdgeProps } from '@xyflow/react';

function FloatingEdge({ id, source, target, style }: EdgeProps) {
  const { sourceNode, targetNode } = useStore((s) => ({
    sourceNode: s.nodeLookup.get(source),
    targetNode: s.nodeLookup.get(target),
  }));
  if (!sourceNode || !targetNode) return null;

  const { sx, sy, tx, ty, sourcePos, targetPos } = getEdgeParams(sourceNode, targetNode);
  const [path] = getBezierPath({ sourceX: sx, sourceY: sy, sourcePosition: sourcePos, targetX: tx, targetY: ty, targetPosition: targetPos });

  return <path id={id} className="react-flow__edge-path" d={path} style={style} />;
}
```

## MiniMap with Custom Colors

```tsx
import { MiniMap } from '@xyflow/react';

function nodeColor(node) {
  switch (node.type) {
    case 'ingest': return '#6366f1';
    case 'search': return '#0ea5e9';
    case 'synthesize': return '#10b981';
    default: return '#57534e';
  }
}

<MiniMap
  nodeColor={nodeColor}
  maskColor="rgba(0, 0, 0, 0.7)"
  bgColor="#0a0a0a"
  pannable zoomable
/>
```

## Intersection Detection

```tsx
const { getIntersectingNodes, isNodeIntersecting } = useReactFlow();

const onNodeDrag = useCallback((_, node) => {
  const intersections = getIntersectingNodes(node).map((n) => n.id);
  setNodes((ns) => ns.map((n) => ({
    ...n,
    className: intersections.includes(n.id) ? 'highlight' : '',
  })));
}, []);

<ReactFlow onNodeDrag={onNodeDrag} />
```

## Delete with Confirmation

```tsx
const onBeforeDelete = useCallback(async ({ nodes, edges }) => {
  const confirmDelete = window.confirm(`Delete ${nodes.length} node(s) and ${edges.length} edge(s)?`);
  return confirmDelete; // return false to cancel
}, []);

<ReactFlow onBeforeDelete={onBeforeDelete} />
```

## Streaming Execution State (Pipeline Runner)

```tsx
const { updateNodeData } = useReactFlow();

async function runPipeline(reader: ReadableStreamDefaultReader) {
  const decoder = new TextDecoder();
  let buffer = '';
  let phase: 'events' | 'answer' | 'meta' = 'events';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    if (phase === 'events') {
      const sep = buffer.indexOf('\x1d');
      if (sep !== -1) {
        const lines = buffer.slice(0, sep).split('\n').filter(Boolean);
        for (const line of lines) {
          const event = JSON.parse(line);
          updateNodeData('search-1', { status: 'running', query: event.query });
        }
        buffer = buffer.slice(sep + 1);
        phase = 'answer';
        updateNodeData('search-1', { status: 'done' });
        updateNodeData('synth-1', { status: 'streaming' });
      }
    }

    if (phase === 'answer') {
      const sep = buffer.indexOf('\x1e');
      if (sep !== -1) {
        updateNodeData('synth-1', { status: 'streaming', output: buffer.slice(0, sep) });
        const meta = JSON.parse(buffer.slice(sep + 1));
        updateNodeData('synth-1', { status: 'done', citations: meta.citations });
        phase = 'meta';
      } else {
        updateNodeData('synth-1', { output: buffer });
      }
    }
  }
}
```

## Redux Integration

```ts
import { createSlice, configureStore } from '@reduxjs/toolkit';
import { applyNodeChanges, applyEdgeChanges } from '@xyflow/react';

const flowSlice = createSlice({
  name: 'flow',
  initialState: { nodes: [], edges: [] },
  reducers: {
    onNodesChange: (state, action) => {
      state.nodes = applyNodeChanges(action.payload, state.nodes);
    },
    onEdgesChange: (state, action) => {
      state.edges = applyEdgeChanges(action.payload, state.edges);
    },
  },
});

export const store = configureStore({ reducer: { flow: flowSlice.reducer } });
```

## Node Selection Change

```tsx
import { useOnSelectionChange } from '@xyflow/react';

function SelectionLogger() {
  const onChange = useCallback(({ nodes, edges }) => {
    console.log('Selected:', nodes.map((n) => n.id), edges.map((e) => e.id));
  }, []);

  useOnSelectionChange({ onChange });
  return null;
}
```

## DevTools Pattern (useStore Low-Level)

```tsx
import { useStore, useNodes, ViewportPortal, type ReactFlowState } from '@xyflow/react';
import { shallow } from 'zustand/shallow';

// Read connection state during drag
const selector = (s: ReactFlowState) => ({
  position: s.connectionPosition,
  status: s.connectionStatus,
  startNodeId: s.connectionStartHandle?.nodeId,
});
const connState = useStore(selector, shallow);

// Node count (scalar — no equality fn needed)
const nodeCount = useStore((s) => s.nodes.length);

// NodeInspector overlay
function NodeInspector() {
  const nodes = useNodes();
  return (
    <ViewportPortal>
      {nodes.map((n) => (
        <div key={n.id} style={{
          position: 'absolute',
          transform: `translate(${n.position.x}px, ${n.position.y + (n.measured?.height ?? 0)}px)`,
        }}>
          {n.id}: {JSON.stringify(n.data)}
        </div>
      ))}
    </ViewportPortal>
  );
}
```
