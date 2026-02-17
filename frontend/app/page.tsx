import { IntegrationDemo } from "@/components/integration-demo";
import { ds } from "@/lib/design-system/tokens";

export default function Home() {
  return (
    <main className={ds.shell}>
      <div className={ds.container}>
        <header className="mb-10">
          <h1 className={ds.headerTitle}>
            Synextra <span className={ds.emphasis}>RAG</span> Playground
          </h1>
          <p className={ds.headerSubtitle}>
            Upload documents, choose retrieval mode, and ask questions grounded
            in citations.
          </p>
        </header>
        <IntegrationDemo />
      </div>
    </main>
  );
}
