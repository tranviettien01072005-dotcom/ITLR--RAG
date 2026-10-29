import { afterEach, expect, it, vi } from "vitest";
afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });
it("fails closed without explicit secrets even in development", async () => {
  vi.stubEnv("JWT_SECRET", "");
  await expect(import("./env")).rejects.toThrow("JWT_SECRET");
});
it("rejects known default database credentials", async () => {
  vi.stubEnv("JWT_SECRET", "a".repeat(40));
  vi.stubEnv("ADMIN_PASSCODE", "b".repeat(32));
  vi.stubEnv("DATABASE_URL", "postgresql://postgres:postgres@localhost/db");
  await expect(import("./env")).rejects.toThrow("DATABASE_URL");
});
it("requires an explicit admin passcode", async () => {
  vi.stubEnv("JWT_SECRET", "a".repeat(40)); vi.stubEnv("ADMIN_PASSCODE", "");
  await expect(import("./env")).rejects.toThrow("ADMIN_PASSCODE");
});
it("rejects multiworker configurations with the memory limiter", async () => {
  vi.stubEnv("JWT_SECRET", "a".repeat(40)); vi.stubEnv("ADMIN_PASSCODE", "b".repeat(32));
  vi.stubEnv("DATABASE_URL", "postgresql://app:unique-test-password@localhost/db");
  vi.stubEnv("WEB_CONCURRENCY", "2");
  await expect(import("./env")).rejects.toThrow("one worker");
});
it("requires an explicit HTTPS origin in production", async () => {
  vi.stubEnv("JWT_SECRET", "a".repeat(40)); vi.stubEnv("ADMIN_PASSCODE", "b".repeat(32));
  vi.stubEnv("DATABASE_URL", "postgresql://app:unique-test-password@localhost/db");
  vi.stubEnv("NODE_ENV", "production"); vi.stubEnv("APP_ORIGIN", "");
  await expect(import("./env")).rejects.toThrow("APP_ORIGIN");
});
