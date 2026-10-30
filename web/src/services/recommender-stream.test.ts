import { afterEach, expect, it, vi } from "vitest";
vi.mock("../config/env", () => ({ env: { recommenderUrl: "http://upstream.test" } }));
import { recommender } from "./recommender";
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
it("uses the calibrated search default and preserves explicit thresholds", async () => {
  const fetchMock = vi.fn<typeof fetch>(async () => new Response("{}", { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  await recommender.search("docker");
  await recommender.search("docker", null, 90);
  expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).min_pct).toBe(84);
  expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body)).min_pct).toBe(90);
});
it("requests upstream SSE without waiting for a complete answer", async () => {
  let streamController: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({ start(c) { streamController = c; } });
  const fetchMock = vi.fn().mockResolvedValue(new Response(body, { headers: { "Content-Type": "text/event-stream" } }));
  vi.stubGlobal("fetch", fetchMock);
  const iterator = recommender.chatStream("question", [], new AbortController().signal);
  const firstEvent = iterator.next();
  streamController!.enqueue(new TextEncoder().encode('data: {"type":"sources","sources":[]}\n\n'));
  expect(await firstEvent).toEqual({ value: { type: "sources", sources: [] }, done: false });
  expect(fetchMock).toHaveBeenCalledWith("http://upstream.test/api/chat/stream", expect.objectContaining({ method: "POST", headers: expect.objectContaining({ Accept: "text/event-stream" }) }));
  await iterator.return(undefined);
});
it("aborts upstream fetch when the browser cancels", async () => {
  const input = new AbortController(); let upstreamSignal: AbortSignal;
  vi.stubGlobal("fetch", vi.fn((_url, init) => new Promise((_resolve, reject) => {
    upstreamSignal = init.signal;
    upstreamSignal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
  })));
  const iterator = recommender.chatStream("q", [], input.signal);
  const result = expect(iterator.next()).rejects.toThrow("Aborted");
  input.abort(); await result;
  expect(upstreamSignal!.aborted).toBe(true);
});
it("aborts upstream on the total chat timeout", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", vi.fn((_url, init) => new Promise((_resolve, reject) => {
    init.signal.addEventListener("abort", () => reject(new DOMException("Timeout", "AbortError")));
  })));
  const iterator = recommender.chatStream("q", [], new AbortController().signal);
  const result = expect(iterator.next()).rejects.toThrow("Timeout");
  await vi.advanceTimersByTimeAsync(240001); await result;
  expect(vi.getTimerCount()).toBe(0);
});
it("rejects an HTML login/error response instead of parsing it as tokens", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>error</html>")));
  await expect(recommender.chatStream("q", [], new AbortController().signal).next()).rejects.toThrow("Invalid chat stream response");
});
