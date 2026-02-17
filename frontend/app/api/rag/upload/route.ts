type UploadMode = "embedded" | "vector";

type BackendFailure = {
  code: string;
  message: string;
  recoverable: boolean;
};

function backendBaseUrl() {
  return (process.env.SYNEXTRA_BACKEND_URL ?? "http://localhost:8000").replace(
    /\/$/,
    "",
  );
}

function readUploadMode(value: FormDataEntryValue | null): UploadMode {
  return value === "vector" ? "vector" : "embedded";
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

function parseBackendFailure(raw: unknown): BackendFailure | null {
  if (!raw || typeof raw !== "object") return null;
  const error = (raw as Record<string, unknown>).error;
  if (!error || typeof error !== "object") return null;

  const code = (error as Record<string, unknown>).code;
  const message = (error as Record<string, unknown>).message;
  const recoverable = (error as Record<string, unknown>).recoverable;

  return {
    code: typeof code === "string" ? code : "upstream_error",
    message: typeof message === "string" ? message : "Upstream request failed",
    recoverable: Boolean(recoverable),
  };
}

function isFileLike(value: FormDataEntryValue | null): value is File {
  if (!value || typeof value === "string") return false;
  return typeof (value as File).arrayBuffer === "function";
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
          message: "A PDF file is required",
          recoverable: true,
        },
      },
      400,
    );
  }

  const requestedMode = readUploadMode(incoming.get("retrieval_mode"));
  const backend = backendBaseUrl();

  const uploadForm = new FormData();
  uploadForm.append("file", file, file.name || "upload.pdf");

  const ingestRes = await fetch(`${backend}/v1/rag/pdfs`, {
    method: "POST",
    body: uploadForm,
  });
  const ingestBody = await readBackendBody(ingestRes);

  if (!ingestRes.ok) {
    return new Response(serializeBody(ingestBody), {
      status: ingestRes.status,
      headers: {
        "content-type": ingestRes.headers.get("content-type") ?? "application/json",
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

  const baseResponse = {
    document_id: documentId,
    filename:
      ingestRecord && typeof ingestRecord.filename === "string"
        ? ingestRecord.filename
        : file.name || "upload.pdf",
    page_count:
      ingestRecord && typeof ingestRecord.page_count === "number"
        ? ingestRecord.page_count
        : 0,
    chunk_count:
      ingestRecord && typeof ingestRecord.chunk_count === "number"
        ? ingestRecord.chunk_count
        : 0,
    requested_mode: requestedMode,
    ready_for_chat: true,
    stages: {
      ingestion: { status: "ok" as const },
      embedded: {
        status: "ok" as const,
        indexed_chunk_count:
          embeddedBody &&
          typeof embeddedBody === "object" &&
          typeof (embeddedBody as Record<string, unknown>).indexed_chunk_count ===
            "number"
            ? (embeddedBody as Record<string, unknown>).indexed_chunk_count
            : undefined,
      },
      vector: {
        status: "skipped" as const,
      },
    },
  };

  if (requestedMode === "embedded") {
    return toJsonResponse({
      ...baseResponse,
      effective_mode: "embedded",
    });
  }

  const vectorRes = await fetch(
    `${backend}/v1/rag/documents/${encodeURIComponent(documentId)}/persist/vector-store`,
    {
      method: "POST",
    },
  );
  const vectorBody = await readBackendBody(vectorRes);

  if (vectorRes.ok) {
    const record = vectorBody as Record<string, unknown>;
    return toJsonResponse({
      ...baseResponse,
      effective_mode: "vector",
      stages: {
        ...baseResponse.stages,
        vector: {
          status: "ok" as const,
          vector_store_id:
            typeof record.vector_store_id === "string"
              ? record.vector_store_id
              : undefined,
          file_ids: Array.isArray(record.file_ids)
            ? record.file_ids.filter((id) => typeof id === "string")
            : undefined,
        },
      },
    });
  }

  const failure = parseBackendFailure(vectorBody);
  if (failure?.recoverable) {
    return toJsonResponse({
      ...baseResponse,
      effective_mode: "embedded",
      warning:
        "Vector persistence failed. Falling back to embedded BM25 retrieval.",
      stages: {
        ...baseResponse.stages,
        vector: {
          status: "failed" as const,
          recoverable: true,
          code: failure.code,
          message: failure.message,
        },
      },
    });
  }

  return new Response(serializeBody(vectorBody), {
    status: vectorRes.status,
    headers: {
      "content-type": vectorRes.headers.get("content-type") ?? "application/json",
    },
  });
}
