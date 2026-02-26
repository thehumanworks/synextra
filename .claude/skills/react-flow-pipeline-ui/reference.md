# React Flow API Reference

## Package

```bash
npm install @xyflow/react
```

```tsx
import { ReactFlow, ... } from '@xyflow/react';
import '@xyflow/react/dist/style.css';  // Full styles
// OR import '@xyflow/react/dist/base.css';  // Minimal base, bring your own theme
```

## Core Components

| Component | Purpose |
|-----------|---------|
| `<ReactFlow />` | Main canvas. Controlled: `nodes`, `edges`, `onNodesChange`, `onEdgesChange`. |
| `<ReactFlowProvider>` | Wrap when using `useReactFlow()`. `<ReactFlow>` itself is NOT a provider. |
| `<Background />` | Pattern bg. `variant={BackgroundVariant.Dots\|Lines\|Cross}`, `gap`, `size`, `color`. |
| `<Controls />` | Zoom, fit view, lock. `showZoom`, `showFitView`, `showInteractive`, `position`. |
| `<MiniMap />` | Overview. `nodeColor={(n) => string}`, `pannable`, `zoomable`, `position`. |
| `<Handle />` | Connection point. `type="source\|target"`, `position`, `id`. |
| `<Panel />` | Positioned overlay. `position="top-left\|top-center\|top-right\|bottom-left\|..."`. |
| `<EdgeLabelRenderer>` | Portal for HTML in edges. Children need `pointerEvents: 'all'` + `className="nodrag nopan"`. |
| `<NodeResizer />` | Resize handles on nodes. `isVisible`, `minWidth`, `minHeight`, `keepAspectRatio`. |
| `<NodeResizeControl>` | Custom resize icon. `position`, `variant="handle\|line"`. |
| `<NodeToolbar />` | Toolbar on selected node. `position`, `offset`, `align`, `isVisible`. |
| `<EdgeToolbar />` | Toolbar on edge. `edgeId`, `x`, `y`, `isVisible`. |
| `<ViewportPortal />` | Render elements in viewport coordinate space (for overlays). |

## Hooks

| Hook | Returns | Purpose |
|------|---------|---------|
| `useReactFlow()` | `ReactFlowInstance` | Full API: `getNodes`, `setNodes`, `updateNodeData`, `fitView`, `screenToFlowPosition`, etc. |
| `useNodesState(init)` | `[nodes, setNodes, onNodesChange]` | Controlled node state (prototyping). |
| `useEdgesState(init)` | `[edges, setEdges, onEdgesChange]` | Controlled edge state (prototyping). |
| `useStore(selector, eq?)` | Selected slice | Subscribe to internal Zustand store. Use `shallow` for objects. |
| `useStoreApi()` | `{ getState, setState }` | Imperative store access (no subscription). |
| `useKeyPress(key)` | `boolean` | `'Space'`, `'Meta+s'`, `['Meta', 'Control']`, `['AltLeft+KeyD', 'Backspace']`. |
| `useOnSelectionChange({ onChange })` | void | Selection changes. **Must memoize `onChange` with `useCallback`**. |
| `useOnViewportChange({ onStart, onChange, onEnd })` | void | Viewport changes. |
| `useNodesData(id\|ids)` | `{ id, type, data }` | Read connected nodes' data reactively. |
| `useNodeConnections({ handleType, handleId? })` | `NodeConnection[]` | Connections on a handle. `onConnect`/`onDisconnect` callbacks. |
| `useConnection()` | `ConnectionState` | Active drag connection state (`fromNode`, `toNode`, `inProgress`, `isValid`). |
| `useInternalNode(id)` | `InternalNode` | Access `internals.positionAbsolute`, `measured.width/height`. Re-renders on any node change. |
| `useUpdateNodeInternals()` | `(ids) => void` | Notify React Flow after programmatic handle changes. |
| `useNodesInitialized()` | `boolean` | True after all nodes have been measured. |
| `useViewport()` | `{ x, y, zoom }` | Current viewport (re-renders on viewport change). |
| `useNodeId()` | `string` | Current node's ID (inside custom node). |

## useReactFlow() — Full Instance API

```ts
// Nodes
getNodes(), getNode(id), getInternalNode(id)
setNodes(nodes | fn), addNodes(nodes)
updateNode(id, update, { replace? }), updateNodeData(id, data, { replace? })
deleteElements({ nodes?, edges? }): Promise<{ deletedNodes, deletedEdges }>

// Edges
getEdges(), getEdge(id)
setEdges(edges | fn), addEdges(edges)
updateEdge(id, update, { replace? }), updateEdgeData(id, data, { replace? })

// Viewport
fitView(opts?), zoomIn(opts?), zoomOut(opts?), zoomTo(level, opts?)
setViewport({ x, y, zoom }, opts?), getViewport(), getZoom()
setCenter(x, y, opts?), fitBounds(rect, opts?)
screenToFlowPosition(clientPos), flowToScreenPosition(flowPos)

// Utilities
toObject(): { nodes, edges, viewport }
getIntersectingNodes(nodeOrRect), isNodeIntersecting(nodeOrRect, area)
getNodesBounds(nodes): Rect
getHandleConnections({ type, id, nodeId })
```

All viewport methods accept `{ duration: ms }` for animation.

## Utilities

| Function | Purpose |
|----------|---------|
| `addEdge(connection, edges)` | Add edge to array |
| `reconnectEdge(oldEdge, newConnection, edges)` | Reconnect edge |
| `applyNodeChanges(changes, nodes)` | Apply change array (for custom state management) |
| `applyEdgeChanges(changes, edges)` | Apply edge change array |
| `getOutgoers(node, nodes, edges)` | Nodes reachable from `node` |
| `getIncomers(node, nodes, edges)` | Nodes connecting to `node` |
| `getStraightPath(...)` | `[path, labelX, labelY]` |
| `getSmoothStepPath(...)` | `[path, labelX, labelY]` |
| `getSimpleBezierPath(...)` | `[path, labelX, labelY]` |
| `getBezierPath(...)` | `[path, labelX, labelY]` — cubic bezier |

## Node Shape

```ts
{
  id: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
  type?: string;                     // key in nodeTypes
  parentId?: string;                 // v12 (was parentNode in v11)
  extent?: 'parent' | [[x,y],[x,y]];
  expandParent?: boolean;            // parent grows to fit child
  measured?: { width, height };      // read-only, after layout
  hidden?: boolean;
  selected?: boolean;
  draggable?: boolean;
  selectable?: boolean;
  connectable?: boolean;
  deletable?: boolean;
  focusable?: boolean;
  sourcePosition?: Position;
  targetPosition?: Position;
  origin?: [number, number];         // [0,0]=top-left, [0.5,0.5]=center
  width?: number; height?: number;   // explicit dimensions (SSR)
  style?: CSSProperties;
  className?: string;
}
```

## Edge Shape

```ts
{
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  type?: string;                     // key in edgeTypes
  animated?: boolean;
  hidden?: boolean;
  selected?: boolean;
  deletable?: boolean;
  reconnectable?: boolean | 'source' | 'target';
  data?: Record<string, unknown>;
  label?: ReactNode;
  labelStyle?: CSSProperties;
  labelBgPadding?: [number, number];
  labelBgBorderRadius?: number;
  labelBgStyle?: CSSProperties;
  markerStart?: EdgeMarker;
  markerEnd?: EdgeMarker;
  style?: CSSProperties;
  interactionWidth?: number;         // hit area width (default: 20)
}
```

## Key ReactFlow Props

| Prop | Type | Default | Purpose |
|------|------|---------|---------|
| `colorMode` | `'light'\|'dark'\|'system'` | `'light'` | Built-in dark mode |
| `nodeTypes` | `Record<string, Component>` | — | Custom node components (**module scope**) |
| `edgeTypes` | `Record<string, Component>` | — | Custom edge components (**module scope**) |
| `defaultEdgeOptions` | `DefaultEdgeOptions` | — | Applied to all new edges |
| `isValidConnection` | `(conn) => boolean` | — | Connection validation |
| `connectionLineType` | `ConnectionLineType` | `Bezier` | Drag line style |
| `connectionLineComponent` | `Component` | — | Custom connection line |
| `connectionMode` | `'strict'\|'loose'` | `'strict'` | `'loose'` allows source-to-source |
| `connectionRadius` | `number` | `20` | Snap-to-handle distance |
| `fitView` | `boolean` | `false` | Fit on mount |
| `fitViewOptions` | `FitViewOptions` | — | `{ padding, minZoom, maxZoom, duration, nodes }` |
| `snapToGrid` | `boolean` | `false` | Snap nodes |
| `snapGrid` | `[number, number]` | `[15, 15]` | Grid size |
| `nodeOrigin` | `[number, number]` | `[0, 0]` | `[0.5, 0.5]` for center |
| `minZoom` | `number` | `0.5` | |
| `maxZoom` | `number` | `2` | |
| `deleteKeyCode` | `KeyCode\|null` | `'Backspace'` | Delete selection |
| `selectionKeyCode` | `KeyCode\|null` | `'Shift'` | Selection box |
| `multiSelectionKeyCode` | `KeyCode\|null` | `Meta/Control` | Multi-select |
| `panActivationKeyCode` | `KeyCode\|null` | `'Space'` | Hold to pan |
| `panOnDrag` | `boolean\|number[]` | `true` | `[1,2]` = middle+right click |
| `panOnScroll` | `boolean` | `false` | Figma-like: scroll to pan |
| `selectionOnDrag` | `boolean` | `false` | Figma-like: drag to select |
| `selectNodesOnDrag` | `boolean` | `true` | |
| `selectionMode` | `'full'\|'partial'` | `'full'` | |
| `onlyRenderVisibleElements` | `boolean` | `false` | Viewport culling |
| `elevateNodesOnSelect` | `boolean` | `true` | |
| `edgesReconnectable` | `boolean` | `false` | Allow edge reconnection |
| `nodesFocusable` | `boolean` | `true` | Tab navigation |
| `edgesFocusable` | `boolean` | `true` | Tab navigation |
| `autoPanOnNodeDrag` | `boolean` | `true` | |
| `autoPanOnConnect` | `boolean` | `true` | |
| `onBeforeDelete` | `(params) => Promise<boolean>` | — | Confirm deletion |
| `onInit` | `(instance) => void` | — | Called when flow is ready |

## Enums

```ts
import { MarkerType, ConnectionLineType, BackgroundVariant, Position, SelectionMode, ConnectionMode } from '@xyflow/react';

MarkerType.Arrow          // open arrowhead
MarkerType.ArrowClosed    // filled arrowhead

ConnectionLineType.Bezier, .Straight, .Step, .SmoothStep, .SimpleBezier

BackgroundVariant.Dots, .Lines, .Cross

Position.Left, .Right, .Top, .Bottom

SelectionMode.Full, .Partial

ConnectionMode.Strict, .Loose
```

## Accessibility

Built-in: Tab navigation, Enter/Space to select, Arrow keys to move, Escape to deselect, ARIA descriptions.

```tsx
<ReactFlow
  nodesFocusable={true}
  edgesFocusable={true}
  disableKeyboardA11y={false}
  ariaLabelConfig={{
    'node.a11yDescription.default': 'Press Enter to select',
    'controls.zoomIn.ariaLabel': 'Zoom In',
    // ... full config available
  }}
/>
```

## Testing

```ts
// setupTests.ts — mock ResizeObserver for JSDOM
class ResizeObserver { observe() {} unobserve() {} disconnect() {} }
window.ResizeObserver = ResizeObserver;
```

```tsx
import { render, screen } from '@testing-library/react';
import { ReactFlow, ReactFlowProvider } from '@xyflow/react';

test('renders nodes', () => {
  render(
    <ReactFlowProvider>
      <ReactFlow nodes={[{ id: '1', data: { label: 'Node 1' }, position: { x: 0, y: 0 } }]} edges={[]} />
    </ReactFlowProvider>
  );
  expect(screen.getByText('Node 1')).toBeInTheDocument();
});
```

## SSR / Next.js

Supported since v12. Requirements:
1. Mark components `'use client'`
2. Provide explicit `width`/`height` on nodes (no ResizeObserver on server)
3. Container must have explicit CSS dimensions
4. Use `ReactFlowProvider` with `initialNodes`, `initialEdges`, `initialWidth`, `initialHeight`, `fitView`
