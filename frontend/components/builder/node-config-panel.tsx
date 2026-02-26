"use client";

import { useEffect, useMemo, useState } from "react";

import { usePipelineStore } from "@/lib/builder/store";
import type { AgentToolType, AppNode, ParallelSearchQuery } from "@/lib/builder/types";
import { AGENT_TOOL_OPTIONS } from "@/lib/builder/types";

type NodeConfigPanelProps = {
  onClose: () => void;
};

function slugify(value: string): string {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return normalized || "agent-node";
}

function buildOutputFilename(label: string, nodeId: string): string {
  return `${slugify(label)}-${slugify(nodeId)}-output.txt`;
}

export function NodeConfigPanel({ onClose }: NodeConfigPanelProps) {
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId);
  const nodes = usePipelineStore((s) => s.nodes);
  const updateNodeData = usePipelineStore((s) => s.updateNodeData);
  const removeNodes = usePipelineStore((s) => s.removeNodes);
  const setSelectedNodeId = usePipelineStore((s) => s.setSelectedNodeId);

  const nodeId = selectedNodeId;
  const node = nodes.find((n) => n.id === nodeId) as AppNode | undefined;

  const data = useMemo(
    () => (node?.data ?? {}) as Record<string, unknown>,
    [node?.data],
  );
  const nodeType = node?.type;

  const [queriesDraft, setQueriesDraft] = useState(() =>
    JSON.stringify((data.queries as ParallelSearchQuery[] | undefined) ?? [], null, 2),
  );
  const [queriesError, setQueriesError] = useState<string | null>(null);
  const [fullOutputOpen, setFullOutputOpen] = useState(false);
  const [outputSaveError, setOutputSaveError] = useState<string | null>(null);

  useEffect(() => {
    setQueriesDraft(
      JSON.stringify((data.queries as ParallelSearchQuery[] | undefined) ?? [], null, 2),
    );
    setQueriesError(null);
  }, [node?.id, data.queries]);

  const agentOutput =
    nodeType === "agent" && typeof data.output === "string" ? data.output : "";

  useEffect(() => {
    setFullOutputOpen(false);
    setOutputSaveError(null);
  }, [node?.id, agentOutput]);

  if (!node || !nodeId || !nodeType) return null;
  const activeNodeId = nodeId;

  function handleChange(key: string, value: unknown) {
    updateNodeData(activeNodeId, { [key]: value });
  }

  function handleDelete() {
    removeNodes([activeNodeId]);
    setSelectedNodeId(null);
  }

  function saveQueriesDraft() {
    try {
      const parsed = JSON.parse(queriesDraft);
      if (!Array.isArray(parsed)) {
        throw new Error("Queries must be a JSON array");
      }
      setQueriesError(null);
      handleChange("queries", parsed);
    } catch (err) {
      setQueriesError(err instanceof Error ? err.message : String(err));
    }
  }

  function saveOutputToFile() {
    if (!agentOutput) return;

    let blobUrl: string | null = null;
    let link: HTMLAnchorElement | null = null;

    try {
      const filename = buildOutputFilename(String(data.label ?? "agent-node"), activeNodeId);
      const blob = new Blob([agentOutput], { type: "text/plain;charset=utf-8" });
      blobUrl = URL.createObjectURL(blob);
      link = document.createElement("a");
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      setOutputSaveError(null);
    } catch (err) {
      setOutputSaveError(err instanceof Error ? err.message : "Failed to save output.");
    } finally {
      if (link?.isConnected) {
        link.remove();
      }
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
      }
    }
  }

  return (
    <>
      <aside className="flex h-full min-h-0 w-full flex-col gap-3 overflow-y-auto rounded-lg border border-stone-800 bg-stone-950 p-4 lg:w-72">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-stone-200">
          {(data.label as string) || nodeType}
        </h2>
        <button onClick={onClose} className="text-stone-500 hover:text-stone-300">
          &#x2715;
        </button>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-xs text-stone-400">Label</span>
        <input
          value={String(data.label ?? "")}
          onChange={(e) => handleChange("label", e.target.value)}
          className="nodrag rounded-md border border-stone-700 bg-stone-900 px-2 py-1 text-sm text-stone-200 focus:border-sky-500 focus:outline-none"
        />
      </label>

      {nodeType === "bm25_search" && (
        <>
          <InputField
            label="Query Template"
            value={String(data.queryTemplate ?? "{query}")}
            onChange={(value) => handleChange("queryTemplate", value)}
          />
          <NumberField
            label="Top-K"
            value={Number(data.topK ?? 8)}
            min={1}
            onChange={(value) => handleChange("topK", value)}
          />
        </>
      )}

      {nodeType === "read_document" && (
        <>
          <NumberField
            label="Page"
            value={Number(data.page ?? 0)}
            min={0}
            onChange={(value) => handleChange("page", value)}
          />
          <NumberField
            label="Start Line"
            value={Number(data.startLine ?? 1)}
            min={1}
            onChange={(value) => handleChange("startLine", value)}
          />
          <NumberField
            label="End Line"
            value={Number(data.endLine ?? 1)}
            min={1}
            onChange={(value) => handleChange("endLine", value)}
          />
          <InputField
            label="Document ID (optional)"
            value={String(data.documentId ?? "")}
            onChange={(value) => handleChange("documentId", value)}
          />
        </>
      )}

      {nodeType === "parallel_search" && (
        <>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-stone-400">Queries (JSON array)</span>
            <textarea
              value={queriesDraft}
              onChange={(e) => setQueriesDraft(e.target.value)}
              className="nodrag min-h-40 rounded-md border border-stone-700 bg-stone-900 px-2 py-1 font-mono text-xs text-stone-200 focus:border-sky-500 focus:outline-none"
            />
          </label>
          <button
            onClick={saveQueriesDraft}
            className="rounded-md border border-stone-700 bg-stone-900 px-2.5 py-1 text-xs text-stone-300 hover:bg-stone-800"
          >
            Apply Query JSON
          </button>
          {queriesError && <p className="text-xs text-red-400">{queriesError}</p>}
        </>
      )}

      {nodeType === "agent" && (
        <>
          <InputField
            label="Prompt Template"
            value={String(data.promptTemplate ?? "{query}")}
            onChange={(value) => handleChange("promptTemplate", value)}
          />
          <SelectField
            label="Reasoning Effort"
            value={String(data.reasoningEffort ?? "medium")}
            options={["none", "low", "medium", "high", "xhigh"]}
            onChange={(value) => handleChange("reasoningEffort", value)}
          />
          <CheckboxField
            label="Enable Review Flag"
            checked={Boolean(data.reviewEnabled)}
            onChange={(value) => handleChange("reviewEnabled", value)}
          />
          <ToolSelector
            selected={(data.tools as AgentToolType[] | undefined) ?? []}
            onChange={(tools) => handleChange("tools", tools)}
          />
          {agentOutput ? (
            <div className="flex flex-col gap-2 rounded-md border border-stone-700 bg-stone-900/70 p-2">
              <div className="text-xs text-stone-400">Latest Agent Output</div>
              <div className="line-clamp-3 whitespace-pre-wrap text-xs text-stone-300">
                {agentOutput}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setFullOutputOpen(true)}
                  className="rounded-md border border-stone-700 bg-stone-900 px-2 py-1 text-xs text-stone-200 hover:bg-stone-800"
                >
                  View Full Output
                </button>
                <button
                  onClick={saveOutputToFile}
                  className="rounded-md border border-stone-700 bg-stone-900 px-2 py-1 text-xs text-stone-200 hover:bg-stone-800"
                >
                  Save Output to File
                </button>
              </div>
              {outputSaveError && <p className="text-xs text-red-400">{outputSaveError}</p>}
            </div>
          ) : (
            <div className="rounded-md border border-stone-800 bg-stone-900/50 px-2 py-1 text-xs text-stone-500">
              No agent output yet.
            </div>
          )}
        </>
      )}

      <button
        onClick={handleDelete}
        className="mt-auto rounded-md border border-red-900 bg-red-950/50 px-3 py-1.5 text-xs text-red-400 hover:bg-red-900/50"
      >
        Delete Node
      </button>
      </aside>

      {fullOutputOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Full Agent Output"
            className="flex max-h-[85vh] w-full max-w-4xl flex-col rounded-lg border border-stone-700 bg-stone-950"
          >
            <div className="flex items-center justify-between border-b border-stone-800 px-4 py-3">
              <h3 className="text-sm font-semibold text-stone-200">Full Agent Output</h3>
              <div className="flex gap-2">
                <button
                  onClick={saveOutputToFile}
                  className="rounded-md border border-stone-700 bg-stone-900 px-2.5 py-1 text-xs text-stone-200 hover:bg-stone-800"
                >
                  Save Output to File
                </button>
                <button
                  onClick={() => setFullOutputOpen(false)}
                  className="rounded-md border border-stone-700 bg-stone-900 px-2.5 py-1 text-xs text-stone-200 hover:bg-stone-800"
                >
                  Close
                </button>
              </div>
            </div>
            {outputSaveError && (
              <p className="border-b border-stone-800 px-4 py-2 text-xs text-red-400">
                {outputSaveError}
              </p>
            )}
            <pre
              data-testid="full-agent-output"
              className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap p-4 text-sm text-stone-200"
            >
              {agentOutput}
            </pre>
          </div>
        </div>
      )}
    </>
  );
}

function InputField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-stone-400">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="nodrag rounded-md border border-stone-700 bg-stone-900 px-2 py-1 text-sm text-stone-200 focus:border-sky-500 focus:outline-none"
      />
    </label>
  );
}

function NumberField({
  label,
  value,
  min,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-stone-400">{label}</span>
      <input
        type="number"
        value={Number.isFinite(value) ? value : min}
        min={min}
        onChange={(e) => onChange(Number(e.target.value))}
        className="nodrag rounded-md border border-stone-700 bg-stone-900 px-2 py-1 text-sm text-stone-200 focus:border-sky-500 focus:outline-none"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-stone-400">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="nodrag rounded-md border border-stone-700 bg-stone-900 px-2 py-1 text-sm text-stone-200 focus:border-sky-500 focus:outline-none"
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </label>
  );
}

function CheckboxField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="nodrag h-3.5 w-3.5 rounded border-stone-600 bg-stone-900 text-sky-500 focus:ring-sky-500"
      />
      <span className="text-xs text-stone-400">{label}</span>
    </label>
  );
}

function ToolSelector({
  selected,
  onChange,
}: {
  selected: AgentToolType[];
  onChange: (tools: AgentToolType[]) => void;
}) {
  function toggle(tool: AgentToolType) {
    if (selected.includes(tool)) {
      onChange(selected.filter((t) => t !== tool));
    } else {
      onChange([...selected, tool]);
    }
  }

  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="text-xs text-stone-400">Tools</legend>
      {AGENT_TOOL_OPTIONS.map((option) => (
        <label key={option.value} className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={selected.includes(option.value)}
            onChange={() => toggle(option.value)}
            className="nodrag h-3.5 w-3.5 rounded border-stone-600 bg-stone-900 text-sky-500 focus:ring-sky-500"
          />
          <span className="text-xs text-stone-300">{option.label}</span>
        </label>
      ))}
    </fieldset>
  );
}
