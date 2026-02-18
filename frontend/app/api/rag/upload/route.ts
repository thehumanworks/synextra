function backendBaseUrl() {
  return (process.env.SYNEXTRA_BACKEND_URL ?? "http://localhost:8000").replace(
    /\/$/,
    "",
  );
}

function toJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function serializeBody(raw: unknown): string {
  return typeof raw === "string" ? raw : JSON.stringify(raw);
}

async function readBackendBody(res: Response): Promise<unknown> {
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res.text();
}

function isFileLike(value: FormDataEntryValue | null): value is File {
  if (!value || typeof value === "string") return false;
  return typeof value.arrayBuffer === "function";
}

export async function POST(req: Request) {
  const incoming = await req.formData().catch(() => null);
  if (!incoming) {
    return toJsonResponse(
      {
        error: {
          code: "invalid_form_data",
          message: "Request body must be multipart/form-data",
          recoverable: false,
        },
      },
      400,
    );
  }

  const file = incoming.get("file");
  if (!isFileLike(file)) {
    return toJsonResponse(
      {
        error: {
          code: "file_required",
          message: "A document file is required",
          recoverable: true,
        },
      },
      400,
    );
  }

  const backend = backendBaseUrl();

  // Step 1: Ingest document (extract + chunk + store page texts).
  const uploadForm = new FormData();
  uploadForm.append("file", file, file.name || "upload");

  const ingestRes = await fetch(`${backend}/v1/rag/documents`, {
    method: "POST",
    body: uploadForm,
  });
  const ingestBody = await readBackendBody(ingestRes);

  if (!ingestRes.ok) {
    return new Response(serializeBody(ingestBody), {
      status: ingestRes.status,
      headers: {
        "content-type":
          ingestRes.headers.get("content-type") ?? "application/json",
      },
    });
  }

  const ingestRecord =
    ingestBody && typeof ingestBody === "object"
      ? (ingestBody as Record<string, unknown>)
      : null;
  const documentId =
    ingestRecord && typeof ingestRecord.document_id === "string"
      ? ingestRecord.document_id
      : "";

  if (!documentId) {
    return toJsonResponse(
      {
        error: {
          code: "invalid_ingestion_response",
          message: "Backend ingestion response missing document_id",
          recoverable: false,
        },
      },
      502,
    );
  }

  // Step 2: Persist to BM25 embedded store.
  const embeddedRes = await fetch(
    `${backend}/v1/rag/documents/${encodeURIComponent(documentId)}/persist/embedded`,
    {
      method: "POST",
    },
  );
  const embeddedBody = await readBackendBody(embeddedRes);

  if (!embeddedRes.ok) {
    return new Response(serializeBody(embeddedBody), {
      status: embeddedRes.status,
      headers: {
        "content-type":
          embeddedRes.headers.get("content-type") ?? "application/json",
      },
    });
  }

  return toJsonResponse({
    document_id: documentId,
    filename:
      ingestRecord && typeof ingestRecord.filename === "string"
        ? ingestRecord.filename
        : file.name || "upload",
    page_count:
      ingestRecord && typeof ingestRecord.page_count === "number"
        ? ingestRecord.page_count
        : 0,
    chunk_count:
      ingestRecord && typeof ingestRecord.chunk_count === "number"
        ? ingestRecord.chunk_count
        : 0,
    effective_mode: "embedded",
    ready_for_chat: true,
    stages: {
      ingestion: { status: "ok" as const },
      embedded: {
        status: "ok" as const,
        indexed_chunk_count:
          embeddedBody &&
          typeof embeddedBody === "object" &&
          typeof (embeddedBody as Record<string, unknown>)
            .indexed_chunk_count === "number"
            ? (embeddedBody as Record<string, unknown>).indexed_chunk_count
            : undefined,
      },
    },
  });
}
