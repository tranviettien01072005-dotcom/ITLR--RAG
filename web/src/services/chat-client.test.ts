import { readFileSync } from "node:fs";
import vm from "node:vm";
import { resolve } from "node:path";
import { expect, it } from "vitest";

it.each([{ tail: [0xff] }, { tail: [0xe2, 0x82] }])("rejects corrupt UTF-8 in the browser (%j)", async ({ tail }) => {
  const ui = client();
  const stream = new ReadableStream<Uint8Array>({ start(controller) {
    controller.enqueue(new TextEncoder().encode('data: {"type":"final","response":"ok"}\n\n'));
    controller.enqueue(new Uint8Array(tail));
    controller.close();
  } });
  await expect(ui.consume(new Response(stream, { headers: { "content-type": "text/event-stream" } }), () => {})).rejects.toThrow();
});
class Element {
  textContent = ""; children: Element[] = []; href = ""; dataset = {}; className = "";
  appendChild(child: Element) { this.children.push(child); }
  replaceChildren() { this.children = []; }
  set innerHTML(_value: string) { throw new Error("Unsafe HTML sink"); }
}
function client() {
  const context = vm.createContext({ URL, TextDecoder, Number, window: {}, document: { createElement: () => new Element() } });
  vm.runInContext(readFileSync(resolve(__dirname, "../public/chat-stream.js"), "utf8"), context);
  return vm.runInContext("window.ITLRChatStream", context);
}
it("renders untrusted source fields as text and restricts source URLs", () => {
  const ui = client(); const target = new Element();
  ui.sourcesInto(target, [{ item_id: 7, title: "<img onerror=alert(1)>", excerpt: "<script>x</script>", url: "javascript:alert(1)" }]);
  const card = target.children[1];
  expect(card.children[0].textContent).toContain("<img onerror=alert(1)>");
  expect(card.children[1].textContent).toBe("<script>x</script>");
  expect(card.children.map(c => c.href).filter(Boolean)).toEqual(["/courses/7"]);
  expect(ui.safeSourceUrl("//evil.test")).toBe("");
  expect(ui.safeSourceUrl("https://example.org/docs")).toBe("https://example.org/docs");
});
it("reads real token events, then replaces provisional output with the final response", async () => {
  const ui = client(); const types: string[] = []; let text = "";
  const bytes = new TextEncoder().encode('data: {"type":"sources","sources":[]}\r\n\r\ndata: {"type":"text","text":"draft"}\n\ndata: {"type":"final","response":"refusal"}\n\ndata: {"type":"done"}\n\n');
  const stream = new ReadableStream({ start(c) { for (const byte of bytes) c.enqueue(new Uint8Array([byte])); c.close(); } });
  await ui.consume(new Response(stream, { headers: { "content-type": "text/event-stream" } }), (event: { type: string; text: string; response: string }) => {
    types.push(event.type);
    if (event.type === "text") text += event.text;
    if (event.type === "final") text = event.response;
  });
  expect(types).toEqual(["sources", "text", "final", "done"]);
  expect(text).toBe("refusal");
});
it("reports interrupted streams and server failures instead of retrying generation", async () => {
  const ui = client();
  await expect(ui.consume(new Response('data: {"type":"text","text":"draft"}\n\n', { headers: { "content-type": "text/event-stream" } }), () => {})).rejects.toThrow("gián đoạn");
  await expect(ui.consume(new Response('data: {"type":"error","error":"service unavailable"}\n\n', { headers: { "content-type": "text/event-stream" } }), () => {})).rejects.toThrow("service unavailable");
});

it("rejects a final event whose terminal done frame was lost", async () => {
  await expect(client().consume(new Response('data: {"type":"final","response":"ok"}\n\n',
    { headers: { "content-type": "text/event-stream" } }), () => {})).rejects.toThrow("gián đoạn");
});

it("rejects an oversized complete frame before delivering it", async () => {
  const ui = client();
  let delivered = false;
  const frame = `data: ${JSON.stringify({ type: "final", response: "x".repeat(1_200_000) })}\n\n`;
  await expect(ui.consume(new Response(frame, { headers: { "content-type": "text/event-stream" } }), () => { delivered = true; })).rejects.toThrow();
  expect(delivered).toBe(false);
});
