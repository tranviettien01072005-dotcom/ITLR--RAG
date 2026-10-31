import { expect, it, vi } from "vitest";
import type { Request, Response } from "express";

vi.mock("../config/env", () => ({ env: { jwtSecret: "x".repeat(40), adminPasscode: "admin-test-passcode" } }));
vi.mock("../db/pool", () => ({ query: vi.fn() }));

import { hasAdminAccess, loadUser, passcodeMatches, requireAdminAccess, requireAuth, signToken } from "./auth";
import { query } from "../db/pool";

const user = { id: 1, email: "learner@example.org", name: "Learner", role: "admin" as const };

it.each(["/api/chat", "/api/chat/stream"])("blocks unauthenticated access to %s", originalUrl => {
  const redirect = vi.fn(), next = vi.fn();
  requireAuth({ originalUrl } as Request, { redirect } as unknown as Response, next);
  expect(redirect).toHaveBeenCalledWith("/login?next=" + encodeURIComponent(originalUrl));
  expect(next).not.toHaveBeenCalled();
});

it("uses the current account role after an admin demotion", async () => {
  vi.mocked(query).mockResolvedValueOnce([{ ...user, role: "user" }]);
  const req = { cookies: { token: signToken(user) }, path: "/api/attachments/1" } as unknown as Request;
  const res = { locals: {} } as Response;
  await loadUser(req, res, vi.fn());
  expect(req.user?.role).toBe("user");
  expect(res.locals.user?.role).toBe("user");
});

it("does not authenticate a deleted account using its unexpired cookie", async () => {
  vi.mocked(query).mockResolvedValueOnce([]);
  const req = { cookies: { token: signToken(user) }, path: "/api/chat" } as unknown as Request;
  const res = { locals: {} } as Response;
  await loadUser(req, res, vi.fn());
  expect(req.user).toBeUndefined();
  expect(res.locals.user).toBeNull();
});

it("compares admin passcodes without leaking length", () => {
  expect(passcodeMatches("admin-test-passcode")).toBe(true);
  expect(passcodeMatches("wrong")).toBe(false);
  expect(passcodeMatches("")).toBe(false);
  expect(passcodeMatches(undefined)).toBe(false);
});

it("only accepts current-version admin cookies signed with the app secret", async () => {
  const jwt = (await import("jsonwebtoken")).default;
  const admin = jwt.sign({ adm: true, v: 2 }, "x".repeat(40));
  const stale = jwt.sign({ adm: true, v: 1 }, "x".repeat(40));
  const forged = jwt.sign({ adm: true, v: 2 }, "y".repeat(40));
  expect(hasAdminAccess({ cookies: { adm: admin } } as never)).toBe(true);
  expect(hasAdminAccess({ cookies: { adm: stale } } as never)).toBe(false);
  expect(hasAdminAccess({ cookies: { adm: forged } } as never)).toBe(false);
  expect(hasAdminAccess({ cookies: {} } as never)).toBe(false);

  const redirect = vi.fn();
  requireAdminAccess({ cookies: {} } as never, { redirect } as never, vi.fn());
  expect(redirect).toHaveBeenCalledWith("/admin/login");
});

it("rejects a token issued before the account's sessions were revoked", async () => {
  vi.mocked(query).mockResolvedValueOnce([{ ...user, token_version: 1 }]);
  const stale = signToken({ ...user, token_version: 0 });
  const req = { cookies: { token: stale }, path: "/api/chat" } as unknown as Request;
  const res = { locals: {} } as Response;
  await loadUser(req, res, vi.fn());
  expect(req.user).toBeUndefined();
});

it("accepts a token whose version matches the stored account version", async () => {
  vi.mocked(query).mockResolvedValueOnce([{ ...user, token_version: 2 }]);
  const current = signToken({ ...user, token_version: 2 });
  const req = { cookies: { token: current }, path: "/api/chat" } as unknown as Request;
  const res = { locals: {} } as Response;
  await loadUser(req, res, vi.fn());
  expect(req.user?.id).toBe(1);
});
