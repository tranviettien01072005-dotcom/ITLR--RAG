import { beforeEach, expect, it, vi } from "vitest";
import type { Request, Response } from "express";

const mocks = vi.hoisted(() => ({ query: vi.fn() }));
vi.mock("../db/pool", () => ({ query: mocks.query }));
vi.mock("../middleware/auth", () => ({
  requireAuth: (_req: unknown, _res: unknown, next: () => void) => next(),
  requireAdminAccess: (_req: unknown, _res: unknown, next: () => void) => next(),
  ADM_VER: 2,
  passcodeMatches: () => true,
}));
vi.mock("../middleware/uploads", () => ({ validateUploads: (_req: unknown, _res: unknown, next: () => void) => next() }));
vi.mock("../services/dataset", async () => ({
  ...(await vi.importActual<typeof import("../services/dataset")>("../services/dataset")),
  appendCatalogRow: vi.fn(),
}));

import { adminRouter } from "./admin.routes";
import { apiRouter } from "./api.routes";

const mockedQuery = vi.mocked(mocks.query);

function response() {
  const res = { status: vi.fn(), json: vi.fn(), redirect: vi.fn() };
  res.status.mockReturnValue(res);
  return res;
}
function handler(router: typeof apiRouter, path: string) {
  return router.stack.find(layer => layer.route?.path === path)!.route!.stack.at(-1)!.handle;
}
function sqlCalls() {
  return mockedQuery.mock.calls.map(call => String(call[0]));
}

beforeEach(() => mockedQuery.mockReset());

it("refuses to complete a lesson that is not approved", async () => {
  mockedQuery.mockResolvedValueOnce([{ course_id: 10, approved: false }]);
  const res = response();
  await handler(apiRouter, "/lessons/:id/complete")(
    { params: { id: "5" }, body: {}, user: { id: 7 } } as unknown as Request,
    res as unknown as Response,
    vi.fn(),
  );
  expect(res.status).toHaveBeenCalledWith(404);
  expect(mockedQuery).toHaveBeenCalledTimes(1);
});

it("computes progress from approved lessons only in one atomic upsert", async () => {
  mockedQuery
    .mockResolvedValueOnce([{ course_id: 10, approved: true }])
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([{ status: "in_progress", progress: 50 }]);
  const res = response();
  await handler(apiRouter, "/lessons/:id/complete")(
    { params: { id: "5" }, body: {}, user: { id: 7 } } as unknown as Request,
    res as unknown as Response,
    vi.fn(),
  );
  const sql = sqlCalls().join("\n");
  expect(sql).toMatch(/count\(\*\) FILTER \(WHERE l\.approved AND EXISTS[\s\S]*lp\.user_id = \$1/);
  expect(sqlCalls().filter(text => text.startsWith("INSERT INTO enrollments"))).toHaveLength(1);
  expect(res.json).toHaveBeenCalledWith({ ok: true, done: true, status: "in_progress", progress: 50 });
});

it("resyncs every affected enrollment when a lesson is approved", async () => {
  mockedQuery.mockResolvedValueOnce([{ course_id: 10 }]).mockResolvedValueOnce([]);
  const res = response();
  await handler(adminRouter, "/lessons/:id/approve")(
    { params: { id: "3" }, headers: {}, get: () => undefined } as unknown as Request,
    res as unknown as Response,
    vi.fn(),
  );
  expect(mockedQuery.mock.calls[0][0]).toMatch(/UPDATE lessons[\s\S]*RETURNING course_id/);
  const sync = sqlCalls().find(text => text.includes("DISTINCT user_id FROM lesson_progress"));
  expect(sync).toBeDefined();
});

it("resyncs every affected enrollment when a lesson is deleted", async () => {
  mockedQuery
    .mockResolvedValueOnce([{ course_id: 10, added_by: 7 }])
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([{ status: "in_progress", progress: 50 }]);
  const res = response();
  await handler(apiRouter, "/lessons/:id")(
    { params: { id: "5" }, user: { id: 7, role: "user" } } as unknown as Request,
    res as unknown as Response,
    vi.fn(),
  );
  expect(res.json).toHaveBeenCalledWith({ ok: true, status: "in_progress", progress: 50 });
  const sync = sqlCalls().find(text => text.includes("DISTINCT user_id FROM lesson_progress"));
  expect(sync).toBeDefined();
});

it("reserves deletion of an approved lesson to admins", async () => {
  mockedQuery.mockResolvedValueOnce([{ course_id: 10, added_by: 7, approved: true }]);
  const res = response();
  await handler(apiRouter, "/lessons/:id")(
    { params: { id: "5" }, user: { id: 7, role: "user" } } as unknown as Request,
    res as unknown as Response,
    vi.fn(),
  );
  expect(res.status).toHaveBeenCalledWith(403);
  expect(mockedQuery).toHaveBeenCalledTimes(1);
});
