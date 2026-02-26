/**
 * Module-level store for File objects selected by ingest nodes.
 * We can't put File objects in Zustand/React Flow node data because
 * they aren't serializable (structuredClone, JSON.stringify both fail).
 */
const files = new Map<string, File>();

export function setNodeFile(nodeId: string, file: File) {
  files.set(nodeId, file);
}

export function getNodeFile(nodeId: string): File | undefined {
  return files.get(nodeId);
}

export function clearNodeFile(nodeId: string) {
  files.delete(nodeId);
}

export function clearAllNodeFiles() {
  files.clear();
}
