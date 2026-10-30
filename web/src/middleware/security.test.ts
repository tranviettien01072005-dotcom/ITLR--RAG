import { beforeEach, expect, it, vi } from "vitest";

vi.mock("../config/env", () => ({ env: { isProd: false } }));

import { csrfProtection } from "./security";

const TOKEN = "a".repeat(64);

function response() {
  const res = {
    locals: {} as Record<string, unknown>,
    cookie: vi.fn(),
    statusCode: 0,
    body: undefined as unknown,
    status(code: number) { this.statusCode = code; return this; },
    json(payload: unknown) { this.body = payload; },
    render(_view: string, data: unknown) { this.body = data; },
  };
  return res;
}

let next: ReturnType<typeof vi.fn>;
beforeEach(() => { next = vi.fn(); });

it("issues a CSRF cookie on a safe request", () => {
  const req = { method: "GET", cookies: {}, headers: {}, query: {}, path: "/" };
  const res = response();
  csrfProtection(req as never, res as never, next as never);
  expect(res.cookie).toHaveBeenCalledOnce();
  expect(res.locals.csrfToken).toMatch(/^[a-f0-9]{64}$/);
  expect(next).toHaveBeenCalledOnce();
});

it.each([
  ["/api/chat", undefined],
  ["/api/chat", "wrong"],
  ["/learning", undefined],
])("rejects a state-changing request without a matching token (%s, %s)", (path, sent) => {
  const req = {
    method: "POST", cookies: { csrf: TOKEN }, headers: sent ? { "x-csrf-token": sent } : {},
    body: {}, query: {}, path,
  };
  const res = response();
  csrfProtection(req as never, res as never, next as never);
  expect(res.statusCode).toBe(403);
  expect(next).not.toHaveBeenCalled();
});

it("accepts the cookie token echoed in the header or body", () => {
  for (const req of [
    { method: "POST", cookies: { csrf: TOKEN }, headers: { "x-csrf-token": TOKEN }, body: {}, query: {}, path: "/account" },
    { method: "POST", cookies: { csrf: TOKEN }, headers: {}, body: { _csrf: TOKEN }, query: {}, path: "/account" },
  ]) {
    next.mockClear();
    csrfProtection(req as never, response() as never, next as never);
    expect(next).toHaveBeenCalledOnce();
  }
});
