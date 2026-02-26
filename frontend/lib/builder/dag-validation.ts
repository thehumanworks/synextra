import { getOutgoers, type Node, type Edge, type Connection } from "@xyflow/react";

/**
 * Returns a connection validator that prevents cycles in the graph.
 * Pipelines must be DAGs — cycles would cause infinite execution loops.
 */
export function createDagValidator(nodes: Node[], edges: Edge[]) {
  return (connection: Edge | Connection): boolean => {
    const target = nodes.find((n) => n.id === connection.target);
    if (!target) return true;

    const hasCycle = (node: Node, visited = new Set<string>()): boolean => {
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
}
