import { beforeEach, expect, it, vi } from "vitest";

const db = vi.hoisted(() => ({ query: vi.fn(async () => []) }));
vi.mock("../config/env", () => ({
  env: { adminPasscode: "admin-test-passcode", jwtSecret: "x".repeat(40), isProd: false, appOrigin: "https://app.test" },
}));
vi.mock("../db/pool", () => ({ query: db.query }));
vi.mock("../middleware/uploads", () => ({ validateUploads: (_req: unknown, _res: unknown, next: () => void) => next() }));
vi.mock("../services/dataset", () => ({ extractText: vi.fn(), appendCatalogRow: vi.fn() }));
vi.mock("../middleware/security", () => ({ authLimiter: (_req: unknown, _res: unknown, next: () => void) => next() }));

import { adminRouter } from "./admin.routes";

function handler(path: string, method: "get" | "post") {
  const found = adminRouter.stack.find((layer) => layer.route?.path === path &&
    (layer.route as unknown as { methods: Record<string, boolean> }).methods[method]);
  return found!.route!.stack.at(-1)!.handle as (req: never, res: never, next: never) => Promise<void>;
}

function response() {
  return {
    statusCode: 0,
    cookie: vi.fn(),
    redirect: vi.fn(),
    render: vi.fn(),
    send: vi.fn(),
    setHeader: vi.fn(),
    status(code: number) { this.statusCode = code; return this; },
  };
}

beforeEach(() => db.query.mockClear());

it("rejects a wrong admin passcode and accepts the configured one", async () => {
  const login = handler("/login", "post");

  const bad = response();
  await login({ body: { passcode: "wrong" } } as never, bad as never, vi.fn() as never);
  expect(bad.statusCode).toBe(401);
  expect(bad.render).toHaveBeenCalledWith("admin-login", expect.objectContaining({ error: "Sai passcode." }));
  expect(bad.cookie).not.toHaveBeenCalled();

  const good = response();
  await login({ body: { passcode: "admin-test-passcode" } } as never, good as never, vi.fn() as never);
  expect(good.cookie).toHaveBeenCalledWith("adm", expect.any(String), expect.objectContaining({ httpOnly: true }));
  expect(good.redirect).toHaveBeenCalledWith("/admin");
});

it("does not query storage for an unknown admin file kind", async () => {
  const download = handler("/file/:kind/:id/download", "get");
  const res = response();
  await download({ params: { kind: "evil", id: "1" } } as never, res as never, vi.fn() as never);
  expect(res.statusCode).toBe(404);
  expect(db.query).not.toHaveBeenCalled();
});
