import dagre from "@dagrejs/dagre";
import { type Node, type Edge, Position } from "@xyflow/react";

const DEFAULT_WIDTH = 220;
const DEFAULT_HEIGHT = 80;

export function getLayoutedElements<N extends Node = Node>(
  nodes: N[],
  edges: Edge[],
  direction: "TB" | "LR" = "LR",
): { nodes: N[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 60, ranksep: 80 });

  const isHorizontal = direction === "LR";

  for (const node of nodes) {
    g.setNode(node.id, {
      width: node.measured?.width ?? DEFAULT_WIDTH,
      height: node.measured?.height ?? DEFAULT_HEIGHT,
    });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    const w = node.measured?.width ?? DEFAULT_WIDTH;
    const h = node.measured?.height ?? DEFAULT_HEIGHT;
    return {
      ...node,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      position: { x: pos.x - w / 2, y: pos.y - h / 2 },
    } as N;
  });

  return { nodes: layoutedNodes, edges };
}
