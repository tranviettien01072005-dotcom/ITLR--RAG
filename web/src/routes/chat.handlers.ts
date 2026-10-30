import type { Request, Response } from "express";
import { z } from "zod";
import { recommender } from "../services/recommender";
import { renderChatMd, finalChatSchema } from "../services/chat-stream";
import { ownedChatHistory, saveChat } from "../services/chat-history";

const chatSchema = z.object({
  message: z.string().trim().min(1).max(12000),
  history: z.array(z.object({ role: z.enum(["user", "assistant"]), content: z.string().max(12000) })).max(20).optional(),
  conversation_id: z.coerce.number().int().positive().optional(),
});

export async function handleChat(req: Request, res: Response) {
  const parsed = chatSchema.safeParse(req.body);
  if (!parsed.success) return res.status(400).json({ error: "Nội dung tin nhắn không hợp lệ." });
  const { message, conversation_id } = parsed.data;
  const history = await ownedChatHistory(req.user!.id, conversation_id);
  if (history === null) return res.status(404).json({ error: "Không tìm thấy cuộc trò chuyện." });
  try {
    const data = finalChatSchema.parse({ ...await recommender.chat(message, history), type: "final" });
    const id = await saveChat(req.user!.id, conversation_id, message, data.response, { sources: data.sources, generation_mode: data.generation_mode, citation_validation: data.citation_validation });
    res.json({ ...data, response_html: renderChatMd(data.response, data.sources), conversation_id: id });
  } catch {
    res.status(502).json({ error: "Không hoàn tất được câu trả lời hoặc lưu lịch sử. Hãy thử lại." });
  }
}

export async function handleChatStream(req: Request, res: Response) {
  const parsed = chatSchema.safeParse(req.body);
  if (!parsed.success) return res.status(400).json({ error: "Nội dung tin nhắn không hợp lệ." });
  const { message, conversation_id } = parsed.data;
  const history = await ownedChatHistory(req.user!.id, conversation_id);
  if (history === null) return res.status(404).json({ error: "Không tìm thấy cuộc trò chuyện." });
  const controller = new AbortController();
  const disconnect = () => controller.abort();
  res.on("close", disconnect);
  res.status(200).set({
    "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "private, no-store, no-transform",
    Connection: "keep-alive", "X-Accel-Buffering": "no",
  });
  res.flushHeaders();
  const started = performance.now();
  let sourceMs: number | null = null, firstTokenMs: number | null = null;
  const write = (data: unknown) => { if (!res.destroyed) res.write(`data: ${JSON.stringify(data)}\n\n`); };
  const heartbeat = setInterval(() => { if (!res.destroyed) res.write(": ping\n\n"); }, 15000);
  try {
    for await (const event of recommender.chatStream(message, history, controller.signal)) {
      if (controller.signal.aborted) break;
      if (event.type === "sources") sourceMs = performance.now() - started;
      if (event.type === "text" && firstTokenMs === null) firstTokenMs = performance.now() - started;
      if (event.type === "error") throw new Error("Upstream generation failed");
      if (event.type === "final") {
        const id = await saveChat(req.user!.id, conversation_id, message, event.response, { sources: event.sources, generation_mode: event.generation_mode, citation_validation: event.citation_validation });
        write({ ...event, response_html: renderChatMd(event.response, event.sources), conversation_id: id,
          timings: { sources_ms: sourceMs, first_token_ms: firstTokenMs, total_ms: performance.now() - started } });
      } else {
        write(event);
      }
    }
  } catch {
    if (!controller.signal.aborted) write({ type: "error", error: "Không hoàn tất được câu trả lời hoặc lưu lịch sử. Hãy thử lại." });
  } finally {
    clearInterval(heartbeat);
    controller.abort();
    res.off("close", disconnect);
    res.end();
  }
}
