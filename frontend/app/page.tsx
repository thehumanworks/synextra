import { DocumentChatWorkspace } from "@/components/document-chat-workspace";

export default function Home() {
  return (
    <main className="min-h-screen bg-black px-4 py-8 text-stone-100 md:px-6 md:py-10">
      <div className="mx-auto w-full max-w-4xl">
        <header className="mb-6 space-y-2 md:mb-8">
          <h1 className="stone-gradient-text text-4xl font-semibold tracking-tight md:text-5xl">
            Synextra
          </h1>
          <p className="text-sm text-stone-400 md:text-base">Chat with your documents.</p>
        </header>

        <DocumentChatWorkspace />
      </div>
    </main>
  );
}
