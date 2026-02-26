# Layout Algorithms

## Dagre (Simple DAG Layout)

```bash
npm install @dagrejs/dagre
```

```tsx
import dagre from '@dagrejs/dagre';
import { type Node, type Edge, Position } from '@xyflow/react';

const g = new dagre.graphlib.Graph();
g.setDefaultEdgeLabel(() => ({}));

export function getLayoutedElements<N extends Node = Node>(
  nodes: N[], edges: Edge[], direction: 'TB' | 'LR' = 'LR',
): { nodes: N[]; edges: Edge[] } {
  g.setGraph({ rankdir: direction, nodesep: 60, ranksep: 80 });
  const isH = direction === 'LR';

  nodes.forEach((n) => g.setNode(n.id, {
    width: n.measured?.width ?? 172,
    height: n.measured?.height ?? 36,
  }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);

  return {
    nodes: nodes.map((n) => {
      const pos = g.node(n.id);
      const w = n.measured?.width ?? 172;
      const h = n.measured?.height ?? 36;
      return {
        ...n,
        targetPosition: isH ? Position.Left : Position.Top,
        sourcePosition: isH ? Position.Right : Position.Bottom,
        position: { x: pos.x - w / 2, y: pos.y - h / 2 },
      } as N;
    }),
    edges,
  };
}
```

Call `fitView({ duration: 300 })` after applying layout. Use `node.measured.width/height` (v12).

Dagre converts center coordinates — React Flow needs top-left, hence the `pos.x - w/2` transform.

## ELK (Advanced Layout with Edge Routing)

```bash
npm install elkjs
```

```tsx
import ELK from 'elkjs/lib/elk.bundled.js';
import { useCallback, useLayoutEffect } from 'react';
import { ReactFlowProvider, useReactFlow, useNodesState, useEdgesState, Panel } from '@xyflow/react';

const elk = new ELK();

const elkOptions = {
  'elk.algorithm': 'layered',
  'elk.layered.spacing.nodeNodeBetweenLayers': '100',
  'elk.spacing.nodeNode': '80',
};

async function getLayoutedElements(nodes, edges, options = {}) {
  const isHorizontal = options?.['elk.direction'] === 'RIGHT';
  const graph = {
    id: 'root',
    layoutOptions: options,
    children: nodes.map((node) => ({
      ...node,
      width: node.measured?.width ?? 150,
      height: node.measured?.height ?? 50,
    })),
    edges,
  };

  const layoutedGraph = await elk.layout(graph);

  return {
    nodes: layoutedGraph.children.map((node) => ({
      ...nodes.find((n) => n.id === node.id),
      position: { x: node.x, y: node.y },
    })),
    edges: layoutedGraph.edges,
  };
}

function LayoutFlow() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const { fitView } = useReactFlow();

  const onLayout = useCallback(({ direction, useInitialNodes = false }) => {
    const opts = { 'elk.direction': direction, ...elkOptions };
    const ns = useInitialNodes ? initialNodes : nodes;
    const es = useInitialNodes ? initialEdges : edges;

    getLayoutedElements(ns, es, opts).then(({ nodes, edges }) => {
      setNodes(nodes);
      setEdges(edges);
      window.requestAnimationFrame(() => fitView());
    });
  }, [nodes, edges]);

  useLayoutEffect(() => {
    onLayout({ direction: 'DOWN', useInitialNodes: true });
  }, []);

  return (
    <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} fitView>
      <Panel position="top-right">
        <button onClick={() => onLayout({ direction: 'DOWN' })}>Vertical</button>
        <button onClick={() => onLayout({ direction: 'RIGHT' })}>Horizontal</button>
      </Panel>
    </ReactFlow>
  );
}
```

### ELK Algorithms

| Algorithm | Best For |
|-----------|----------|
| `layered` | DAGs, pipelines (default) |
| `stress` | General graphs |
| `mrtree` | Tree structures |
| `radial` | Radial/circular layouts |
| `force` | Force-directed |

### ELK vs Dagre

| Feature | Dagre | ELK |
|---------|-------|-----|
| Dynamic node sizes | Yes | Yes |
| Sub-flow layouting | Partial | Full |
| Edge routing | No | Yes (orthogonal) |
| Async | No | Yes (Promise-based) |
| Bundle size | Small | Larger |

Use **dagre** for simple pipeline layouts. Use **ELK** when you need edge routing, orthogonal edges, or complex sub-flow layouts.

## Auto-Layout Hook Pattern

```tsx
import { useNodesInitialized, useReactFlow } from '@xyflow/react';

export function useAutoLayout() {
  const nodesInitialized = useNodesInitialized();
  const { getNodes, getEdges, setNodes, fitView } = useReactFlow();

  useEffect(() => {
    if (!nodesInitialized) return;
    const layoutNodes = async () => {
      const { nodes } = getLayoutedElements(getNodes(), getEdges(), 'LR');
      setNodes(nodes);
      setTimeout(() => fitView({ duration: 800 }), 100);
    };
    layoutNodes();
  }, [nodesInitialized]);
}
```

## Fitting After Layout

```tsx
// Pattern 1: requestAnimationFrame (most reliable)
window.requestAnimationFrame(() => fitView());

// Pattern 2: with animation
window.requestAnimationFrame(() => fitView({ duration: 300 }));

// Pattern 3: fit to specific nodes
fitView({ nodes: [{ id: 'node-1' }, { id: 'node-2' }], padding: 0.2 });
```
