import { afterEach, expect, it, vi } from "vitest";

vi.mock("nodemailer", () => ({ default: { createTransport: vi.fn() } }));

import { isMailConfigured, sendResetLink } from "./mailer";

afterEach(() => {
  delete process.env.SMTP_USER;
  delete process.env.SMTP_PASS;
});

it("reports SMTP as unconfigured when credentials are missing", async () => {
  delete process.env.SMTP_USER;
  delete process.env.SMTP_PASS;
  expect(isMailConfigured()).toBe(false);
  await expect(sendResetLink("a@example.org", "https://app.test/reset/x", 15)).resolves.toBe(false);
});

it("reads SMTP credentials at call time, not only at module load", () => {
  process.env.SMTP_USER = "fixture@example.org";
  process.env.SMTP_PASS = "fixture-app-password";
  expect(isMailConfigured()).toBe(true);
});
