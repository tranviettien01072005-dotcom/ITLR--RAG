import { expect, it, vi } from "vitest";

const client = vi.hoisted(() => ({
  query: vi.fn(async (..._args: unknown[]) => ({ rows: [] })),
  release: vi.fn(),
}));
vi.mock("pg", () => ({
  Pool: class {
    on(): void {}
    async connect() { return client; }
    async query() { return { rows: [] }; }
  },
}));
vi.mock("../config/env", () => ({ env: { databaseUrl: "postgresql://user:password@127.0.0.1:1/db" } }));

import { withTransaction } from "./pool";

it("commits a successful unit of work and releases the client", async () => {
  client.query.mockClear();
  client.release.mockClear();
  const result = await withTransaction(async q => {
    await q("SELECT 1");
    return "ok";
  });
  expect(result).toBe("ok");
  expect(client.query.mock.calls.map(call => call[0])).toEqual(["BEGIN", "SELECT 1", "COMMIT"]);
  expect(client.release).toHaveBeenCalledTimes(1);
});

it("rolls back and releases the client when the unit of work throws", async () => {
  client.query.mockClear();
  client.release.mockClear();
  await expect(withTransaction(async () => { throw new Error("boom"); })).rejects.toThrow("boom");
  expect(client.query.mock.calls.map(call => call[0])).toEqual(["BEGIN", "ROLLBACK"]);
  expect(client.release).toHaveBeenCalledTimes(1);
});
