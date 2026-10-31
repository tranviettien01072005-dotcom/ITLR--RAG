import { beforeEach, expect, it, vi } from "vitest";
import type { Request, Response } from "express";

const mocks = vi.hoisted(() => ({ query: vi.fn() }));
vi.mock("bcryptjs", () => ({ default: { hash: async () => "hash", compare: async () => true } }));
vi.mock("../config/env", () => ({ env: { appOrigin: "https://app.test", jwtSecret: "x".repeat(40) } }));
vi.mock("../db/pool", () => ({ query: mocks.query, withTransaction: vi.fn() }));
vi.mock("../middleware/auth", () => ({
  requireAuth: (_req: unknown, _res: unknown, next: () => void) => next(),
  signToken: () => "token",
  setAuthCookie: vi.fn(),
  clearAuthCookie: vi.fn(),
}));
vi.mock("../services/mailer", () => ({ isMailConfigured: () => false, mailConfigured: () => false, sendResetLink: async () => false }));
vi.mock("../middleware/security", () => ({ authLimiter: (_req: unknown, _res: unknown, next: () => void) => next() }));

import { clearAuthCookie } from "../middleware/auth";
import { authRouter } from "./auth.routes";

function handler(path: string) {
  return authRouter.stack.find(layer => layer.route?.path === path)!.route!.stack.at(-1)!.handle;
}

beforeEach(() => mocks.query.mockReset());

it("revokes every session for the account on explicit logout-all", async () => {
  mocks.query.mockResolvedValueOnce([{ token_version: 3 }]);
  const res = { clearCookie: vi.fn(), redirect: vi.fn() };
  await handler("/account/logout-all")(
    { user: { id: 7, email: "a@example.org", name: "A", role: "user", token_version: 2 } } as unknown as Request,
    res as unknown as Response,
    vi.fn(),
  );
  expect(mocks.query.mock.calls[0][0]).toMatch(/UPDATE users SET token_version = token_version \+ 1/);
  expect(mocks.query.mock.calls[0][1]).toEqual([7]);
  expect(vi.mocked(clearAuthCookie)).toHaveBeenCalledWith(res);
  expect(res.redirect).toHaveBeenCalledWith("/login");
});
