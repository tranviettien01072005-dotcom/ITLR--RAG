import { expect, it, vi } from "vitest";
vi.mock("../config/env", () => ({ env: { appOrigin: "https://app.test", jwtSecret: "x".repeat(40) } }));
vi.mock("../db/pool", () => ({ query: vi.fn(async (sql: string) => sql.startsWith("SELECT id FROM users") ? [{ id: 1 }] : []) }));
vi.mock("../services/mailer", () => ({ mailConfigured: () => false, sendResetLink: async () => false }));
vi.mock("../middleware/security", () => ({ authLimiter: (_req: unknown, _res: unknown, next: () => void) => next() }));
import { authRouter } from "./auth.routes";
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
