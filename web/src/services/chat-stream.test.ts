import { expect, it } from "vitest";
import { readChatEvents } from "./chat-stream";

it.each([{ tail: [0xff] }, { tail: [0xe2, 0x82] }])("rejects corrupt UTF-8 after a final event (%j)", async ({ tail }) => {
  const stream = new ReadableStream<Uint8Array>({ start(controller) {
    controller.enqueue(new TextEncoder().encode('data: {"type":"final","response":"ok"}\n\n'));
    controller.enqueue(new Uint8Array(tail));
    controller.close();
  } });
  await expect((async () => {
    for await (const _event of readChatEvents(stream)) { /* consume */ }
  })()).rejects.toThrow();
});

function body(parts: string[]) {
  return new ReadableStream<Uint8Array>({ start(controller) {
    for (const part of parts) controller.enqueue(new TextEncoder().encode(part));
    controller.close();
  } });
}
it.each(["sources", "meta", "error", "done"])("rejects %s after the done event", async type => {
  const tail = type === "sources" ? { type, sources: [] } : { type };
  const frames = [{ type: "final", response: "complete" }, { type: "done" }, tail];
  await expect((async () => {
    for await (const _event of readChatEvents(body(frames.map(event => `data: ${JSON.stringify(event)}\n\n`)))) { /* consume */ }
  })()).rejects.toThrow();
});
it("forwards early sources before tokens across fragmented CRLF frames", async () => {
  const events = [];
  for await (const event of readChatEvents(body([
    'data: {"type":"sources","sources":[{"item_id":7,"title":"Docs","excerpt":"Reference"}]}\r',
    '\n\r\ndata: {"type":"text","text":"Xin chào"}\n\n',
    'data: {"type":"final","response":"Final [item_id:7]"}\n\ndata: {"type":"done"}\n\n',
  ]))) events.push(event);
  expect(events.map(e => e.type)).toEqual(["sources", "text", "final", "done"]);
  expect(events[1]).toMatchObject({ text: "Xin chào" });
});
it.each([
  'data: {"type":"text","text":3}\n\n',
  'data: {"type":"sources","sources":[{"item_id":"<script>","title":"bad"}]}\n\n',
  'data: not-json\n\n',
  'data: {"type":"text","text":"unfinished"}\n\n',
])("rejects invalid or incomplete upstream streams", async value => {
  await expect((async () => { for await (const _event of readChatEvents(body([value]))) { /* consume */ } })()).rejects.toThrow();
});
it("cancels the upstream body when the consumer stops", async () => {
  let cancelled = false;
  const stream = new ReadableStream<Uint8Array>({ start(c) { c.enqueue(new TextEncoder().encode('data: {"type":"text","text":"hi"}\n\n')); }, cancel() { cancelled = true; } });
  for await (const _event of readChatEvents(stream)) break;
  expect(cancelled).toBe(true);
});

it("rejects EOF after final without the terminal done event", async () => {
  await expect((async () => {
    for await (const _event of readChatEvents(body(['data: {"type":"final","response":"ok"}\n\n']))) { /* consume */ }
  })()).rejects.toThrow("Incomplete chat stream");
});

import { renderChatMd } from "./chat-stream";
it("links only retrieved citation IDs and escapes model markup", () => {
  const html = renderChatMd('<img src=x onerror=alert(1)> [item_id:7] [item_id:99] [bad](javascript:alert(1))', [{ item_id: 7 }]);
  expect(html).toContain('href="/courses/7"');
  expect(html).not.toContain('href="/courses/99"');
  expect(html).not.toContain('<img');
  expect(html).not.toContain('href="javascript:');
});

it("preserves multibyte UTF-8 split across network chunks", async () => {
  const response = "T\u00e0i li\u1ec7u \u65e5\u672c\u8a9e";
  const stream = new ReadableStream<Uint8Array>({ start(controller) {
    for (const byte of new TextEncoder().encode(`data: ${JSON.stringify({ type: "final", response })}\n\ndata: {"type":"done"}\n\n`)) {
      controller.enqueue(new Uint8Array([byte]));
    }
    controller.close();
  } });
  const events = [];
  for await (const event of readChatEvents(stream)) events.push(event);
  expect(events).toEqual([expect.objectContaining({ type: "final", response }), { type: "done" }]);
});

it("keeps source code and citation-shaped text literal inside code, linking only prose", () => {
  const response = '> ```text\n> __enter__() [item_id:7]\n> ```\n\n`[item_id:7]` [item_id:7]';
  const html = renderChatMd(response, [{ item_id: 7 }]);
  expect(html).toContain('__enter__() [item_id:7]');
  expect(html).toContain('<code>[item_id:7]</code>');
  expect(html).not.toContain('[item_id:7](/courses/7)');
  expect(html.match(/href="\/courses\/7"/g)).toHaveLength(1);
});
