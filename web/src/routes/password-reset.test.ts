import { beforeEach, expect, it, vi } from "vitest";
import type { Request, Response } from "express";

const tx = vi.hoisted(() => ({
  q: vi.fn(),
  withTransaction: vi.fn(),
  send: vi.fn(async () => true),
  query: vi.fn(),
}));
vi.mock("bcryptjs", () => ({ default: { hash: async () => "new-hash", compare: async () => true } }));
vi.mock("../config/env", () => ({ env: { appOrigin: "https://app.test", jwtSecret: "x".repeat(40) } }));
vi.mock("../db/pool", () => ({ query: tx.query, withTransaction: tx.withTransaction }));
vi.mock("../services/mailer", () => ({ isMailConfigured: () => true, mailConfigured: () => true, sendResetLink: tx.send }));
vi.mock("../middleware/security", () => ({ authLimiter: (_req: unknown, _res: unknown, next: () => void) => next() }));

import { authRouter } from "./auth.routes";

function handler(path: string) {
  const route = authRouter.stack
    .filter(layer => layer.route?.path === path && (layer.route as unknown as { methods: Record<string, boolean> }).methods.post)
    .at(-1)!.route!;
  return route.stack.at(-1)!.handle;
}
function response() {
  const res = { render: vi.fn(), redirect: vi.fn(), clearCookie: vi.fn() };
  return res;
}
const TOKEN = "a".repeat(64);

beforeEach(() => {
  tx.q.mockReset();
  tx.query.mockReset();
  tx.withTransaction.mockReset();
  tx.send.mockClear();
  tx.withTransaction.mockImplementation(async (fn: (q: unknown) => unknown) => fn(tx.q));
});

it("claims the reset token, changes the password and revokes sessions in one transaction", async () => {
  tx.query.mockResolvedValueOnce([{ user_id: 4 }]);
  tx.q.mockResolvedValueOnce([{ id: 9 }]).mockResolvedValueOnce([]).mockResolvedValueOnce([]);
  const res = response();
  await handler("/reset/:token")(
    { params: { token: TOKEN }, body: { password: "Strong!Pass1", confirm: "Strong!Pass1" } } as unknown as Request,
    res as unknown as Response,
    vi.fn(),
  );
  expect(tx.withTransaction).toHaveBeenCalledTimes(1);
  const statements = tx.q.mock.calls.map(call => String(call[0]));
  expect(statements.some(text => /UPDATE users SET password_hash[\s\S]*token_version = token_version \+ 1/.test(text))).toBe(true);
  expect(statements.some(text => /UPDATE password_resets SET used_at = now\(\)/.test(text))).toBe(true);
  expect(res.clearCookie).toHaveBeenCalledWith("token");
  expect(res.redirect).toHaveBeenCalledWith("/login");
});

it("does not change the password when the token was already claimed", async () => {
  tx.query.mockResolvedValueOnce([{ user_id: 4 }]);
  tx.q.mockResolvedValueOnce([]);
  const res = response();
  await handler("/reset/:token")(
    { params: { token: TOKEN }, body: { password: "Strong!Pass1", confirm: "Strong!Pass1" } } as unknown as Request,
    res as unknown as Response,
    vi.fn(),
  );
  expect(tx.q.mock.calls.some(call => String(call[0]).startsWith("UPDATE users"))).toBe(false);
  expect(res.redirect).not.toHaveBeenCalled();
});

it("throttles repeated reset emails per account without revealing the account", async () => {
  tx.query.mockResolvedValueOnce([{ id: 4 }]).mockResolvedValueOnce([]).mockResolvedValueOnce([]);
  const res = response();
  await handler("/forgot")(
    { body: { email: "learner@example.org" } } as unknown as Request,
    res as unknown as Response,
    vi.fn(),
  );
  expect(tx.query).toHaveBeenCalledTimes(3);
  expect(tx.send).not.toHaveBeenCalled();
  expect(res.render).toHaveBeenCalledWith("auth/forgot", expect.objectContaining({ done: true }));
});

it("prunes expired and used reset tokens before issuing a new one", async () => {
  tx.query
    .mockResolvedValueOnce([{ id: 4 }])
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([{ id: 11 }])
    .mockResolvedValueOnce([]);
  const res = response();
  await handler("/forgot")(
    { body: { email: "learner@example.org" } } as unknown as Request,
    res as unknown as Response,
    vi.fn(),
  );
  const statements = tx.query.mock.calls.map(call => String(call[0]));
  expect(statements.some(text => text.startsWith("DELETE FROM password_resets"))).toBe(true);
  expect(tx.send).toHaveBeenCalledTimes(1);
});
