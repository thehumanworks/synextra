import { describe, expect, it } from "vitest";

import { getLatestUserPrompt, POST } from "@/app/api/chat/route";

describe("getLatestUserPrompt", () => {
  it("returns the most recent user text payload", () => {
    const result = getLatestUserPrompt([
      {
        role: "user",
        parts: [{ type: "text", text: "first" }],
      },
      {
        role: "assistant",
        parts: [{ type: "text", text: "ignore" }],
      },
      {
        role: "user",
        parts: [
          { type: "text", text: "latest" },
          { type: "text", text: "prompt" },
        ],
      },
    ]);

    expect(result).toBe("latest prompt");
  });

  it("returns an empty string for missing user parts", () => {
    const result = getLatestUserPrompt([
      {
        role: "assistant",
        parts: [{ type: "text", text: "no user" }],
      },
      {
        role: "user",
        parts: [{ type: "tool-call", text: "not text" }],
      },
    ]);

    expect(result).toBe("");
  });

  it("trims whitespace from the joined prompt", () => {
    const result = getLatestUserPrompt([
      {
        role: "user",
        parts: [{ type: "text", text: "  question  " }],
      },
    ]);

    expect(result).toBe("question");
  });
});

describe("POST /api/chat", () => {
  it("returns a streaming response for valid payloads", async () => {
    const request = new Request("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({
        messages: [{ role: "user", parts: [{ type: "text", text: "hello" }] }],
      }),
      headers: {
        "content-type": "application/json",
      },
    });

    const response = await POST(request);

    expect(response.status).toBe(200);
  });

  it("handles malformed JSON payloads", async () => {
    const request = new Request("http://localhost/api/chat", {
      method: "POST",
      body: "{",
      headers: {
        "content-type": "application/json",
      },
    });

    const response = await POST(request);

    expect(response.status).toBe(200);
  });
});
