import { createUIMessageStream, createUIMessageStreamResponse } from "ai";

type IncomingPart = {
  type?: string;
  text?: string;
};

type IncomingMessage = {
  role?: string;
  parts?: IncomingPart[];
};

export function getLatestUserPrompt(messages: IncomingMessage[]): string {
  const userMessages = messages.filter((message) => message.role === "user");
  const lastUserMessage = userMessages[userMessages.length - 1];

  if (!lastUserMessage?.parts?.length) {
    return "";
  }

  return lastUserMessage.parts
    .filter((part) => part.type === "text" && typeof part.text === "string")
    .map((part) => part.text)
    .join(" ")
    .trim();
}

export async function POST(request: Request) {
  let latestPrompt = "";

  try {
    const body = (await request.json()) as { messages?: IncomingMessage[] };
    latestPrompt = getLatestUserPrompt(body.messages ?? []);
  } catch {
    latestPrompt = "";
  }

  const stream = createUIMessageStream({
    execute: ({ writer }) => {
      const textId = crypto.randomUUID();
      const responseText = latestPrompt
        ? `Scaffold response to: "${latestPrompt}". Replace this stub in src/app/api/chat/route.ts with streamText(...) + your model provider.`
        : "AI SDK route scaffold is live. Send a prompt to verify the hook wiring.";

      writer.write({ type: "start" });
      writer.write({ type: "text-start", id: textId });
      writer.write({ type: "text-delta", id: textId, delta: responseText });
      writer.write({ type: "text-end", id: textId });
      writer.write({ type: "finish" });
    },
  });

  return createUIMessageStreamResponse({ stream });
}
