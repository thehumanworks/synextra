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

export async function POST(req: Request) {
  const incoming = await req.formData().catch(() => null);
  if (!incoming) {
    return toJsonResponse(
      {
        error: {
          code: "invalid_form_data",
          message: "Request body must be multipart/form-data",
        },
      },
      400,
    );
  }

  const spec = incoming.get("spec");
  if (typeof spec !== "string" || !spec.trim()) {
    return toJsonResponse(
      {
        error: {
          code: "pipeline_spec_required",
          message: "Form field 'spec' is required",
        },
      },
      400,
    );
  }

  const outbound = new FormData();
  outbound.append("spec", spec);
  for (const [key, value] of incoming.entries()) {
    if (key === "spec") continue;
    if (typeof value === "string") {
      outbound.append(key, value);
      continue;
    }
    outbound.append(key, value, value.name || "upload");
  }

  const backend = backendBaseUrl();
  let backendRes: Response;
  try {
    backendRes = await fetch(`${backend}/v1/pipeline/runs/stream`, {
      method: "POST",
      body: outbound,
    });
  } catch {
    return toJsonResponse(
      {
        error: {
          code: "backend_unreachable",
          message: "Failed to reach backend pipeline runtime",
        },
      },
      502,
    );
  }

  if (!backendRes.ok) {
    const errorText = await backendRes.text();
    return new Response(errorText || "Pipeline run request failed", {
      status: backendRes.status,
      headers: {
        "content-type":
          backendRes.headers.get("content-type") ?? "application/json",
      },
    });
  }

  if (!backendRes.body) {
    return toJsonResponse(
      {
        error: {
          code: "empty_backend_stream",
          message: "Backend stream body was empty",
        },
      },
      502,
    );
  }

  return new Response(backendRes.body, {
    status: 200,
    headers: {
      "content-type":
        backendRes.headers.get("content-type") ?? "application/x-ndjson",
      "cache-control": "no-cache",
    },
  });
}
