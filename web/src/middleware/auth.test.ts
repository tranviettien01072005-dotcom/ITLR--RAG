import { expect, it, vi } from "vitest";
import type { Request, Response } from "express";

vi.mock("../config/env", () => ({ env: { jwtSecret: "x".repeat(40) } }));
vi.mock("../db/pool", () => ({ query: vi.fn() }));

import { loadUser, signToken } from "./auth";
import { query } from "../db/pool";

const user = { id: 1, email: "learner@example.org", name: "Learner", role: "admin" as const };

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
