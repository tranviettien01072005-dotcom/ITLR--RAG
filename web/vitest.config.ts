import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    // Tests use mocked database access and must not depend on an operator's .env.
    env: {
      JWT_SECRET: "fixture-only-jwt-secret-for-isolated-tests",
      ADMIN_PASSCODE: "fixture-only-admin-passcode",
      DATABASE_URL: "postgresql://fixture:fixture-only-password@127.0.0.1:1/itlr_test",
    },
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov", "json", "json-summary"],
      include: ["src/**/*.ts"],
      exclude: ["src/**/*.test.ts", "src/server.ts", "src/views/**", "src/public/**"],
    },
  },
});
