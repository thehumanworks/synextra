import { PipelineBuilder } from "@/components/builder/pipeline-builder";

export const metadata = {
  title: "Pipeline Builder | Synextra",
  description: "Visual pipeline builder for document processing workflows.",
};

export default function BuilderPage() {
  return (
    <main className="flex h-dvh flex-col bg-black text-stone-100">
      <header className="flex items-center justify-between border-b border-stone-800 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <h1 className="title-gradient-text text-lg font-semibold tracking-tight">
            Synextra
          </h1>
          <span className="text-xs text-stone-500">Pipeline Builder</span>
        </div>
      </header>
      <div className="flex-1 min-h-0 overflow-hidden p-2 sm:p-3">
        <PipelineBuilder />
      </div>
    </main>
  );
}
