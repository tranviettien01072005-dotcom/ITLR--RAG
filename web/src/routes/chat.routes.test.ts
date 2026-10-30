import { EventEmitter } from "node:events";
import { beforeEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ history: vi.fn(), save: vi.fn(), stream: vi.fn(), chat: vi.fn() }));
vi.mock("../db/pool", () => ({ query: vi.fn() }));
vi.mock("../middleware/auth", () => ({ requireAuth: (_req: unknown, _res: unknown, next: () => void) => next() }));
vi.mock("../services/recommender", () => ({ recommender: { chatStream: mocks.stream, chat: mocks.chat } }));
vi.mock("../services/chat-history", () => ({ ownedChatHistory: mocks.history, saveChat: mocks.save }));
vi.mock("../services/dataset", () => ({ extractText: vi.fn(), appendCatalogRow: vi.fn() }));
import { apiRouter } from "./api.routes";
import { requireAuth } from "../middleware/auth";
it.each(["/chat", "/chat/stream"])("registers authentication first for %s", path => {
  const route = apiRouter.stack.find(layer => layer.route?.path === path)!.route!;
  expect(route.stack).toHaveLength(2);
  expect(route.stack[0].handle).toBe(requireAuth);
});
function handler(path: string) { return apiRouter.stack.find(layer => layer.route?.path === path)!.route!.stack.at(-1)!.handle; }
function response() {
  const events = new EventEmitter();
  const res = Object.assign(events, { status: vi.fn(), json: vi.fn(), set: vi.fn(), flushHeaders: vi.fn(), write: vi.fn(), end: vi.fn(), destroyed: false });
  res.status.mockReturnValue(res); res.set.mockReturnValue(res);
  return res;
}
function request(body: unknown) { return { body, user: { id: 7 } }; }
beforeEach(() => { vi.resetAllMocks(); mocks.history.mockResolvedValue([]); mocks.save.mockResolvedValue(9); });
it.each(["/chat", "/chat/stream"])("rejects messages beyond the FastAPI limit at %s", async path => {
  const res = response();
  await handler(path)(request({ message: "x".repeat(2001) }) as never, res as never, vi.fn());
  expect(res.status).toHaveBeenCalledWith(400);
  expect(mocks.history).not.toHaveBeenCalled();
  expect(mocks.chat).not.toHaveBeenCalled();
  expect(mocks.stream).not.toHaveBeenCalled();
});
it("rejects foreign conversations before contacting the model", async () => {
  mocks.history.mockResolvedValue(null); const res = response();
  await handler("/chat/stream")(request({ message: "hello", conversation_id: 42 }) as never, res as never, vi.fn());
  expect(res.status).toHaveBeenCalledWith(404);
  expect(mocks.stream).not.toHaveBeenCalled(); expect(mocks.save).not.toHaveBeenCalled();
});
it("forwards sources and tokens immediately, saves final under the authenticated owner", async () => {
  const res = response();
  mocks.history.mockResolvedValue([{ role: "user", content: "owned history" }]);
  mocks.stream.mockImplementation(async function* () {
    yield { type: "sources", sources: [{ item_id: 2, title: "Docs" }] };
    expect(res.write).toHaveBeenCalledWith(expect.stringContaining('"type":"sources"'));
    expect(mocks.save).not.toHaveBeenCalled();
    yield { type: "text", text: "draft" };
    yield { type: "final", response: "Valid [item_id:2]", sources: [{ item_id: 2 }], recommendations: [], intent: "learn" };
    yield { type: "done" };
  });
  await handler("/chat/stream")(request({ message: "hello", conversation_id: 9, history: [{ role: "user", content: "forged history" }], user_id: 99 }) as never, res as never, vi.fn());
  expect(mocks.stream).toHaveBeenCalledWith("hello", [{ role: "user", content: "owned history" }], expect.any(AbortSignal));
  expect(mocks.save).toHaveBeenCalledWith(7, 9, "hello", "Valid [item_id:2]", expect.objectContaining({ sources: [{ item_id: 2 }] }));
  const final = res.write.mock.calls.map(call => String(call[0])).find(text => text.includes('"type":"final"'))!;
  expect(final).toContain('/courses/2'); expect(final).toContain('"conversation_id":9'); expect(final).toContain('"timings"');
  expect(res.end).toHaveBeenCalledOnce();
});
it("aborts upstream when the browser disconnects", async () => {
  const res = response(); let signal: AbortSignal | undefined;
  mocks.stream.mockImplementation(async function* (_message, _history, inputSignal) {
    signal = inputSignal; res.emit("close"); yield { type: "text", text: "ignored" };
  });
  await handler("/chat/stream")(request({ message: "hello" }) as never, res as never, vi.fn());
  expect(signal?.aborted).toBe(true); expect(mocks.save).not.toHaveBeenCalled();
});

it("does not persist a final response when upstream subsequently fails", async () => {
  const res = response();
  mocks.stream.mockImplementation(async function* () {
    yield { type: "final", response: "unconfirmed final", sources: [] };
    throw new Error("transport failed before done");
  });
  await handler("/chat/stream")(request({ message: "hello" }) as never, res as never, vi.fn());
  expect(mocks.save).not.toHaveBeenCalled();
  expect(res.write.mock.calls.some(call => String(call[0]).includes('"type":"final"'))).toBe(false);
  expect(res.write).toHaveBeenCalledWith(expect.stringContaining('"type":"error"'));
});
it("reports interrupted upstream and failed persistence explicitly", async () => {
  const res = response();
  mocks.stream.mockImplementation(async function* () { yield { type: "text", text: "draft" }; throw new Error("upstream failed"); });
  await handler("/chat/stream")(request({ message: "hello" }) as never, res as never, vi.fn());
  expect(res.write).toHaveBeenCalledWith(expect.stringContaining('"type":"error"'));
  const failedSave = response(); mocks.save.mockRejectedValue(new Error("database offline"));
  mocks.stream.mockImplementation(async function* () { yield { type: "final", response: "final", sources: [] }; });
  await handler("/chat/stream")(request({ message: "hello" }) as never, failedSave as never, vi.fn());
  expect(failedSave.write).toHaveBeenCalledWith(expect.stringContaining('"type":"error"'));
  expect(failedSave.write.mock.calls.some(call => String(call[0]).includes('"type":"final"'))).toBe(false);
});
