# Performance Optimization

## Architecture

React Flow uses a layered rendering architecture:

1. **NodeRenderer** subscribes only to an array of visible node **IDs** — re-renders only when nodes are added/removed from the viewport.
2. **NodeWrapper** (per node) reads its own data from the internal Zustand store using `shallow` equality — only re-renders when that specific node changes.
3. **EdgeRenderer** follows the same ID-array pattern.

This means: if you have 1000 nodes and drag one, only that one NodeWrapper re-renders.

## Rules

### 1. Memoize custom nodes and edges

```tsx
import { memo } from 'react';

const MyNode = memo(function MyNode({ data }: NodeProps) {
  return <div>{data.label}</div>;
});

// Define nodeTypes at module scope
const nodeTypes = { custom: MyNode };
```

**Never define `nodeTypes` or `edgeTypes` inside a component** — the new object reference causes all nodes to unmount/remount every render.

### 2. Memoize event handlers

```tsx
const onNodeClick = useCallback((event, node) => {
  console.log('Node clicked:', node);
}, []);

const snapGrid = useMemo(() => [20, 20] as [number, number], []);
const defaultEdgeOptions = useMemo(() => ({ animated: true }), []);
```

### 3. Use `useStore` selectors instead of full arrays

```tsx
// BAD — re-renders on every node position change
const nodes = useStore((state) => state.nodes);
const selectedIds = nodes.filter((n) => n.selected).map((n) => n.id);

// GOOD — only re-renders when selection changes
import { shallow } from 'zustand/shallow';
const selectedIds = useStore(
  (s) => s.nodes.filter((n) => n.selected).map((n) => n.id),
  shallow,
);
```

For Zustand stores from `create()`, use `useShallow`:

```tsx
import { useShallow } from 'zustand/react/shallow';

const { nodes, edges } = useStore(
  useShallow((s) => ({ nodes: s.nodes, edges: s.edges })),
);
```

### 4. Use `useStoreApi` for imperative reads (no subscription)

```tsx
import { useStoreApi } from '@xyflow/react';

function MyComponent() {
  const store = useStoreApi();

  const handleClick = () => {
    const { nodes } = store.getState(); // no subscription, no re-render
    console.log('Current nodes:', nodes);
  };
}
```

### 5. Enable viewport culling for large graphs

```tsx
<ReactFlow onlyRenderVisibleElements={true} />
```

Skips rendering nodes/edges outside the viewport. Enabled automatically for 1000+ elements.

### 6. Lazy expand/collapse for hierarchical data

```tsx
const expandNode = (targetNodeId: string) => {
  setNodes((nds) =>
    nds.map((n) =>
      n.data.parentId === targetNodeId ? { ...n, hidden: false } : n,
    ),
  );
};
```

### 7. Simplify node styles for large counts

Complex CSS (box-shadows, gradients, blur) triggers expensive repaints. Use flat colors and thin borders for 500+ nodes.

### 8. Use SVG animateMotion for animated edges

`animated: true` uses `stroke-dasharray` CSS — fine for <100 edges. For more, use the SVG `<animateMotion>` approach from the custom edge pattern.

## Performance Benchmarks

The stress test in `examples/react/src/examples/Stress/` creates a 25x25 grid (625 nodes) and uses `FrameRecorder` with `requestAnimationFrame` to capture per-frame timings during drag operations. Use it as a baseline when optimizing.

## Measured Dimensions

In v12, rendered node dimensions are at `node.measured.width` / `node.measured.height` (not `node.width/height`). These are available after the first layout pass. For SSR or before mount, provide explicit `width`/`height` on the node.
