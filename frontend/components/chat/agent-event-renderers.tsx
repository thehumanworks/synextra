import React from "react";

import type { AgentEvent } from "@/lib/chat/structured-response";
import { cn } from "@/lib/utils";

function EventShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "rounded-2xl",
        "bg-black/30",
        "p-4",
        "ring-1 ring-white/10"
      )}
    >
      <div className="text-xs uppercase tracking-wider text-muted-foreground">
        {title}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function JsonPreview({ value }: { value: unknown }) {
  const json = JSON.stringify(value, null, 2);
  return (
    <pre
      className={cn(
        "max-h-64 overflow-auto",
        "rounded-xl",
        "bg-black/55",
        "p-3",
        "text-xs",
        "font-mono",
        "text-stone-100",
        "ring-1 ring-white/10"
      )}
    >
      <code>{json}</code>
    </pre>
  );
}

function VerifierEvent({ event }: { event: AgentEvent }) {
  return (
    <EventShell title="Verifier">
      <div className="text-sm text-stone-100">
        Verification details were emitted by the agent.
      </div>
      <div className="mt-3">
        <JsonPreview value={event} />
      </div>
    </EventShell>
  );
}

function FixerEvent({ event }: { event: AgentEvent }) {
  return (
    <EventShell title="Fixer">
      <div className="text-sm text-stone-100">
        A post-processing step adjusted the response.
      </div>
      <div className="mt-3">
        <JsonPreview value={event} />
      </div>
    </EventShell>
  );
}

function UnknownEvent({ event }: { event: AgentEvent }) {
  return (
    <EventShell title={`Agent event: ${event.type}`}>
      <JsonPreview value={event} />
    </EventShell>
  );
}

export function renderAgentEvents(events: AgentEvent[]): React.ReactNode {
  if (!events.length) return null;

  return (
    <div className="space-y-3" data-testid="agent-events">
      {events.map((event, idx) => {
        const key = `${event.type}-${idx}`;
        if (event.type === "verifier") return <VerifierEvent key={key} event={event} />;
        if (event.type === "fixer") return <FixerEvent key={key} event={event} />;
        return <UnknownEvent key={key} event={event} />;
      })}
    </div>
  );
}
