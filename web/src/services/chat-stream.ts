import { z } from "zod";
import { renderMd } from "./markdown";

const sourceSchema = z.object({
  item_id: z.number().int().positive(), title: z.string().max(2000),
  excerpt: z.string().max(20000).optional(), url: z.string().max(4000).optional(),
  link: z.string().max(4000).optional(),
}).passthrough();
export type ChatSource = z.infer<typeof sourceSchema>;
export const storedChatSchema = z.object({ sources: z.array(sourceSchema).max(100).default([]), generation_mode: z.string().optional(), citation_validation: z.unknown().optional() });

export function safeSourceUrl(value: string | undefined): string {
  try {
    const url = new URL(value || "");
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : "";
  } catch { return ""; }
}

export const finalChatSchema = z.object({
  type: z.literal("final"), response: z.string().max(1_000_000),
  sources: z.array(sourceSchema).max(100).default([]),
  recommendations: z.array(sourceSchema).max(100).default([]),
  intent: z.string().default("unknown"),
}).passthrough();
const eventSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("sources"), sources: z.array(sourceSchema).max(100) }),
  z.object({ type: z.literal("meta") }).passthrough(),
  z.object({ type: z.literal("text"), text: z.string().max(262144) }),
  finalChatSchema,
  z.object({ type: z.literal("error"), error: z.string().optional(), message: z.string().optional() }),
  z.object({ type: z.literal("done") }),
]);
export type ChatEvent = z.infer<typeof eventSchema>;
export type FinalChat = z.infer<typeof finalChatSchema>;

// Parse SSE incrementally: network chunks need not align with UTF-8 or event boundaries.
export async function* readChatEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let buffer = "", finalized = false, ended = false, totalText = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      let match: RegExpExecArray | null;
      while ((match = /\r?\n\r?\n/.exec(buffer))) {
        const frame = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        if (frame.length > 1_100_000) throw new Error("Stream event too large");
        const data = frame.split(/\r?\n/).filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
        if (!data) continue;
        const event = eventSchema.parse(JSON.parse(data));
        if (ended) throw new Error("Event after stream completion");
        if (finalized && event.type !== "done") throw new Error("Event after final response");
        if (event.type === "text") {
          totalText += event.text.length;
          if (finalized || totalText > 1_000_000) throw new Error("Invalid stream sequence");
        }
        if (event.type === "final") {
          if (finalized) throw new Error("Duplicate final response");
          finalized = true;
        }
        if (event.type === "done" && !finalized) throw new Error("Missing final response");
        if (event.type === "done") ended = true;
        yield event;
      }
      if (buffer.length > 1_100_000) throw new Error("Stream event too large");
    }
    buffer += decoder.decode();
    if (buffer.trim() || !finalized || !ended) throw new Error("Incomplete chat stream");
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export function renderChatMd(response: string, sources: { item_id: number }[]): string {
  const ids = new Set(sources.map(source => source.item_id));
  return renderMd(response.replace(/\[item_id:(\d+)\]/g, (label, raw: string) => {
    const id = Number(raw);
    return ids.has(id) ? `[item_id:${id}](/courses/${id})` : label;
  }));
}
