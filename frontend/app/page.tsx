import { DocumentChatWorkspace } from "@/components/document-chat-workspace";
import { ShaderBackground } from "@/components/ui/shader-background";

export default function Home() {
  return (
    <main className="relative min-h-screen bg-black px-3 py-6 text-stone-100 sm:px-4 sm:py-8 md:px-6 md:py-10">
      <ShaderBackground />
      <div className="relative mx-auto w-full max-w-4xl">
        <header className="mb-5 space-y-1.5 sm:mb-6 md:mb-8">
          <h1 className="title-gradient-text text-5xl font-semibold tracking-tight sm:text-6xl md:text-7xl">
            Synextra
          </h1>
          <p className="text-sm text-stone-400 sm:text-base">Chat with your documents.</p>
        </header>

        <DocumentChatWorkspace />
      </div>
    </main>
  );
}
