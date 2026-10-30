import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import vm from "node:vm";
import { expect, it } from "vitest";

class Element {
  textContent = ""; innerHTML = ""; className = ""; value = "question";
  dataset: Record<string, unknown> = {}; disabled = false; hidden = false;
  children: Element[] = []; listeners: Record<string, (event: { preventDefault(): void }) => void> = {};
  bubble?: Element;
  append(...children: Element[]) { this.children.push(...children); }
  appendChild(child: Element) { this.append(child); }
  replaceChildren() { this.children = []; }
  querySelector(selector: string): Element | null {
    return selector === ".bubble" ? (this.bubble ??= new Element()) : null;
  }
  addEventListener(name: string, callback: (event: { preventDefault(): void }) => void) { this.listeners[name] = callback; }
  getAttribute() { return null; }
  setAttribute() {}
  focus() {}
  matches() { return false; }
}

async function submit(tail: number[] | "done" | "missing") {
  const form = new Element(), input = new Element(), log = new Element(), button = new Element();
  form.querySelector = () => button;
  const nodes: Record<string, Element> = { chatform: form, chatinput: input, chatlog: log, chatstop: new Element() };
  const bytes = new TextEncoder().encode('data: {"type":"text","text":"provisional draft"}\n\ndata: {"type":"final","response":"verified","conversation_id":42}\n\n');
  const response = new Response(new ReadableStream({ start(controller) {
    controller.enqueue(bytes);
    if (tail === "done") controller.enqueue(new TextEncoder().encode('data: {"type":"done"}\n\n'));
    else if (Array.isArray(tail)) controller.enqueue(new Uint8Array(tail));
    controller.close();
  } }), { headers: { "content-type": "text/event-stream" } });
  const history: unknown[] = [];
  const context = vm.createContext({ URL, TextDecoder, ReadableStream, AbortController,
    performance, setInterval, clearInterval, setTimeout,
    fetch: async () => response,
    window: { ReadableStream, AbortController, scrollTo() {}, addEventListener() {},
      history: { replaceState(...args: unknown[]) { history.push(args); } } },
    document: { cookie: "", body: new Element(), createElement: () => new Element(),
      getElementById: (id: string) => nodes[id] ?? null,
      querySelector: () => null, querySelectorAll: () => [], addEventListener() {} },
  });
  for (const file of ["chat-stream.js", "app.js"]) {
    vm.runInContext(readFileSync(resolve(__dirname, "../public", file), "utf8"), context);
  }
  form.listeners.submit({ preventDefault() {} });
  await expect.poll(() => log.children.length === 2 && !button.disabled).toBe(true);
  const container = log.children[1].bubble!;
  return { answer: container.children[1], status: container.children[2], history };
}

it.each([["missing"], [[0xff]], [[0xe2, 0x82]]] as const)("reports invalid completion in the actual chat handler (%j)", async tail => {
  const ui = await submit(typeof tail === "string" ? tail : [...tail]);
  expect(ui.status.textContent).not.toContain("Hoàn tất");
  expect(ui.answer.textContent).toBe("");
  expect(ui.history).toEqual([]);
});

it("confirms completion and conversation only after a valid terminal stream", async () => {
  const ui = await submit("done");
  expect(ui.status.textContent).toContain("Hoàn tất");
  expect(ui.answer.innerHTML).toBe("verified");
  expect(ui.history).toHaveLength(1);
});
