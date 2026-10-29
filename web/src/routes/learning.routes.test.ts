import { beforeEach, expect, it, vi } from "vitest";
vi.mock("../db/pool", () => ({ query: vi.fn() }));
vi.mock("../middleware/auth", () => ({ requireAuth: (_req: unknown, _res: unknown, next: () => void) => next() }));
import { query } from "../db/pool";
import { learningRouter } from "./learning.routes";

const mockedQuery = vi.mocked(query);
const request = (body: unknown) => ({ body, user: { id: 7 } });
function response() {
  const res = { status: vi.fn(), json: vi.fn() };
  res.status.mockReturnValue(res);
  return res;
}
function handler(path: string) {
  return learningRouter.stack.find(layer => layer.route?.path === path)!.route!.stack.at(-1)!.handle;
}
beforeEach(() => mockedQuery.mockReset());
it("rejects incomplete diagnostics before persistence", async () => {
  const res = response();
  await handler("/api/learning/diagnostic")(request({ track: "python", goal: "Học Python", answers: [0] }) as never, res as never, vi.fn());
  expect(res.status).toHaveBeenCalledWith(400);
  expect(mockedQuery).not.toHaveBeenCalled();
});
it("persists server score against authenticated account and rejects client score override", async () => {
  const res = response();
  mockedQuery.mockResolvedValue([]);
  await handler("/api/learning/diagnostic")(request({ track: "python", goal: "Học Python", answers: [1, 0, 2] }) as never, res as never, vi.fn());
  expect(res.json).toHaveBeenCalledWith({ ok: true, score: 3, level: "intermediate" });
  expect(mockedQuery.mock.calls[0][1]).toEqual([7, "python", "Học Python", 3, "intermediate"]);
  const forged = response();
  await handler("/api/learning/diagnostic")(request({ track: "python", goal: "Học Python", answers: [0, 0, 0], score: 3, user_id: 8 }) as never, forged as never, vi.fn());
  expect(forged.status).toHaveBeenCalledWith(400);
});
it("rejects updates to resources outside the current real roadmap", async () => {
  mockedQuery.mockResolvedValueOnce([{ track: "python", level: "beginner" }]).mockResolvedValueOnce([]);
  const res = response();
  await handler("/api/learning/progress")(request({ course_id: 1, status: "completed", progress: 100 }) as never, res as never, vi.fn());
  expect(res.status).toHaveBeenCalledWith(404);
  expect(mockedQuery.mock.calls).toHaveLength(2);
});
it("updates only the authenticated user's enrollment and reflects persisted progress", async () => {
  mockedQuery.mockResolvedValueOnce([{ track: "python", level: "beginner" }])
    .mockResolvedValueOnce([{ item_id: 101, title: "Python basics", topics: "Python", level: "Beginner", status: "saved", progress: 0 }])
    .mockResolvedValueOnce([{ status: "in_progress", progress: 40 }]);
  const res = response();
  await handler("/api/learning/progress")(request({ course_id: 101, status: "in_progress", progress: 40 }) as never, res as never, vi.fn());
  expect(mockedQuery.mock.calls[2][1]).toEqual([7, 101, "in_progress", 40]);
  expect(res.json).toHaveBeenCalledWith({ ok: true, enrollment: { status: "in_progress", progress: 40 } });
});
it("reloads account goal and existing progress without exposing quiz scoring keys", async () => {
  mockedQuery.mockResolvedValueOnce([{ track: "python", goal: "Read CSV", score: 2, level: "intermediate" }])
    .mockResolvedValueOnce([{ item_id: 101, title: "Python basics", topics: "Python", level: "Beginner", status: "completed", progress: 100 }]);
  const res = { render: vi.fn(), setHeader: vi.fn() };
  await handler("/learning")({ user: { id: 7 }, query: {} } as never, res as never, vi.fn());
  const data = res.render.mock.calls[0][1];
  expect(data.profile.goal).toBe("Read CSV");
  expect(data.roadmap[0].resources[0].progress).toBe(100);
  expect(JSON.stringify(data.quiz)).not.toMatch(/correct|answer/);
  expect(mockedQuery.mock.calls[0][1]).toEqual([7]);
  expect(mockedQuery.mock.calls[1][1]).toEqual([7]);
});
