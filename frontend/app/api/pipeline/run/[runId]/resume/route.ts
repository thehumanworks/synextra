function backendBaseUrl() {
  return (process.env.SYNEXTRA_BACKEND_URL ?? "http://localhost:8000").replace(
    /\/$/,
    "",
  );
}

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params;
  let res: Response;
  try {
    res = await fetch(
      `${backendBaseUrl()}/v1/pipeline/runs/${encodeURIComponent(runId)}/resume`,
      { method: "POST" },
    );
  } catch {
    return new Response(
      JSON.stringify({ error: { code: "backend_unreachable", message: "Failed to reach backend" } }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }
  const body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}
