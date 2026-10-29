import { beforeEach, expect, it, vi } from "vitest";
vi.mock("../db/pool", () => ({ query: vi.fn() }));
vi.mock("../middleware/auth", () => ({ requireAuth: (_req: unknown, _res: unknown, next: () => void) => next() }));
vi.mock("../services/recommender", () => ({ recommender: { suggested: vi.fn().mockResolvedValue({ prompts: [] }) } }));
import { query } from "../db/pool";
import { pagesRouter } from "./pages.routes";
const db = vi.mocked(query);
const handler = pagesRouter.stack.find(layer => layer.route?.path === "/chat")!.route!.stack.at(-1)!.handle;
beforeEach(() => db.mockReset());
it("restores source cards and citation links only from saved validated metadata", async () => {
  db.mockResolvedValueOnce([{ id: 9, title: "Saved chat" }]).mockResolvedValueOnce([{}]).mockResolvedValueOnce([
    { role: "assistant", content: "See [item_id:7] and [item_id:99]", metadata: { sources: [{ item_id: 7, title: "Docs", excerpt: "Real text", url: "https://example.org/docs" }] } },
    { role: "assistant", content: "Legacy [item_id:7]", metadata: {} },
  ]);
  const res = { render: vi.fn() };
  await handler({ user: { id: 2 }, query: { c: "9" } } as never, res as never, vi.fn());
  const data = res.render.mock.calls[0][1];
  expect(data.messages[0].html).toContain('href="/courses/7"');
  expect(data.messages[0].html).not.toContain('href="/courses/99"');
  expect(data.messages[0].sources[0].safe_url).toBe("https://example.org/docs");
  expect(data.messages[1].html).not.toContain("href=");
  expect(db.mock.calls[1][1]).toEqual([9, 2]);
});
it("does not load messages for a foreign conversation", async () => {
  db.mockResolvedValueOnce([]).mockResolvedValueOnce([]);
  const res = { render: vi.fn() };
  await handler({ user: { id: 2 }, query: { c: "99" } } as never, res as never, vi.fn());
  expect(db).toHaveBeenCalledTimes(2);
  expect(res.render.mock.calls[0][1].messages).toEqual([]);
});
it("rejects malformed saved source metadata and executable source URLs", async () => {
  db.mockResolvedValueOnce([]).mockResolvedValueOnce([{}]).mockResolvedValueOnce([
    { role: "assistant", content: "[item_id:7]", metadata: { sources: [{ item_id: "bad", title: "bad" }] } },
    { role: "assistant", content: "[item_id:7]", metadata: { sources: [{ item_id: 7, title: "Docs", url: "javascript:alert(1)" }] } },
  ]);
  const res = { render: vi.fn() };
  await handler({ user: { id: 2 }, query: { c: "9" } } as never, res as never, vi.fn());
  const data = res.render.mock.calls[0][1];
  expect(data.messages[0].sources).toEqual([]);
  expect(data.messages[0].html).not.toContain("href=");
  expect(data.messages[1].sources[0].safe_url).toBe("");
});
