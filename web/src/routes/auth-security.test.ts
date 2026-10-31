import { expect, it, vi } from "vitest";
vi.mock("bcryptjs", () => ({ default: { compare: async () => true } }));
vi.mock("../config/env", () => ({ env: { appOrigin: "https://app.test", jwtSecret: "x".repeat(40) } }));
vi.mock("../db/pool", () => ({ query: vi.fn(async (sql: string) => sql.startsWith("SELECT id FROM users") ? [{ id: 1 }] : []) }));
vi.mock("../services/mailer", () => ({ isMailConfigured: () => false, mailConfigured: () => false, sendResetLink: async () => false }));
vi.mock("../middleware/security", () => ({ authLimiter: (_req: unknown, _res: unknown, next: () => void) => next() }));
import { authRouter } from "./auth.routes";
import { query } from "../db/pool";
it("does not log a reset token when SMTP is unavailable", async () => {
  const log = vi.spyOn(console, "log").mockImplementation(() => {});
  const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
  try {
    const route = authRouter.stack.filter(layer => layer.route?.path === "/forgot").at(-1)!.route!;
    const handler = route.stack.at(-1)!.handle;
    await handler({ body: { email: "learner@example.org" } } as never, { render: () => {} } as never, (() => {}) as never);
    expect(JSON.stringify([...log.mock.calls, ...warn.mock.calls])).not.toMatch(/\/reset\/[a-f0-9]{64}/);
  } finally { log.mockRestore(); warn.mockRestore(); }
});

it.each(["/\\evil.example", "//evil.example"])(
  "keeps login redirects on this origin for %j", async (next) => {
    vi.mocked(query).mockResolvedValueOnce([{ id: 1, email: "learner@example.org", name: "Learner", role: "user", password_hash: "hash" }]);
    const route = authRouter.stack.filter(layer => layer.route?.path === "/login").at(-1)!.route!;
    const redirect = vi.fn();
    await route.stack.at(-1)!.handle(
      { body: { email: "learner@example.org", password: "password", next } } as never,
      { cookie: vi.fn(), redirect } as never, (() => {}) as never,
    );
    expect(new URL(redirect.mock.calls[0][0], "https://app.test").origin).toBe("https://app.test");
  },
);

it("preserves a local login destination and query", async () => {
  vi.mocked(query).mockResolvedValueOnce([{ id: 1, email: "learner@example.org", name: "Learner", role: "user", password_hash: "hash" }]);
  const route = authRouter.stack.filter(layer => layer.route?.path === "/login").at(-1)!.route!;
  const redirect = vi.fn();
  await route.stack.at(-1)!.handle(
    { body: { email: "learner@example.org", password: "password", next: "/learning?track=python" } } as never,
    { cookie: vi.fn(), redirect } as never, (() => {}) as never,
  );
  expect(redirect).toHaveBeenCalledWith("/learning?track=python");
});
