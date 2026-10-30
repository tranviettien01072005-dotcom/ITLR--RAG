import { beforeEach, expect, it, vi } from "vitest";
const db = vi.hoisted(() => ({ query: vi.fn(), client: { query: vi.fn(), release: vi.fn() }, connect: vi.fn() }));
vi.mock("../db/pool", () => ({ query: db.query, pool: { connect: db.connect } }));
import { ownedChatHistory, saveChat } from "./chat-history";
beforeEach(() => { vi.resetAllMocks(); db.connect.mockResolvedValue(db.client); db.client.query.mockResolvedValue({ rows: [{ id: 9 }] }); });
it("does not load another user's history", async () => {
  db.query.mockResolvedValue([]);
  expect(await ownedChatHistory(2, 9)).toBeNull();
  expect(db.query).toHaveBeenCalledExactlyOnceWith(expect.stringContaining("user_id = $2"), [9, 2]);
});
it("loads the authenticated conversation's last twenty messages in chronological order", async () => {
  db.query.mockResolvedValueOnce([{}]).mockResolvedValueOnce([{ role: "assistant", content: "a" }, { role: "user", content: "q" }]);
  expect(await ownedChatHistory(2, 9)).toEqual([{ role: "user", content: "q" }, { role: "assistant", content: "a" }]);
});

it("bounds provider history without changing stored messages or splitting Unicode", async () => {
  const content = "a" + "😀".repeat(2500);
  const rows = [{ role: "assistant", content }];
  db.query.mockResolvedValueOnce([{}]).mockResolvedValueOnce(rows);
  const history = await ownedChatHistory(2, 9);
  expect(history![0].content.length).toBeLessThanOrEqual(4000);
  expect(history![0].content).not.toMatch(/[\uD800-\uDBFF]$/);
  expect(rows[0].content).toBe(content);
});

it("omits empty legacy messages from provider context", async () => {
  db.query.mockResolvedValueOnce([{}]).mockResolvedValueOnce([{ role: "assistant", content: "" }]);
  expect(await ownedChatHistory(2, 9)).toEqual([]);
});
it("locks ownership before saving and commits both messages together", async () => {
  expect(await saveChat(2, 9, "question", "answer")).toBe(9);
  expect(db.client.query.mock.calls[1]).toEqual([expect.stringContaining("user_id = $2 FOR UPDATE"), [9, 2]]);
  expect(db.client.query).toHaveBeenCalledWith(expect.stringContaining("($1,'user',$2,'{}'::jsonb),($1,'assistant',$3,$4::jsonb)"), [9, "question", "answer", "{}"]);
  expect(db.client.query).toHaveBeenLastCalledWith("COMMIT");
  expect(db.client.release).toHaveBeenCalledOnce();
});
it("rejects a deleted or foreign conversation without inserting messages", async () => {
  db.client.query.mockResolvedValueOnce({ rows: [] }).mockResolvedValueOnce({ rows: [] });
  await expect(saveChat(2, 9, "q", "a")).rejects.toThrow("Conversation unavailable");
  expect(db.client.query).toHaveBeenLastCalledWith("ROLLBACK");
  expect(db.client.query.mock.calls.some(call => call[0].startsWith("INSERT"))).toBe(false);
  expect(db.client.release).toHaveBeenCalledOnce();
});
it("rolls back database errors instead of silently dropping history", async () => {
  db.client.query.mockResolvedValueOnce({ rows: [] }).mockResolvedValueOnce({ rows: [{ id: 9 }] }).mockRejectedValueOnce(new Error("write failed"));
  await expect(saveChat(2, undefined, "q", "a")).rejects.toThrow("write failed");
  expect(db.client.query).toHaveBeenLastCalledWith("ROLLBACK");
});
it("stores final source and validation metadata together with the assistant answer", async () => {
  const metadata = { sources: [{ item_id: 7, title: "Docs", excerpt: "reference" }], citation_validation: { status: "valid", semantic_grounding: "not_verified" } };
  await saveChat(2, 9, "q", "[item_id:7]", metadata);
  expect(db.client.query).toHaveBeenCalledWith(expect.stringContaining("metadata)"), [9, "q", "[item_id:7]", JSON.stringify(metadata)]);
});
