import { expect, it, vi } from "vitest";

vi.mock("../config/env", () => ({ env: { appOrigin: "https://app.test" } }));
vi.mock("../db/pool", () => ({ query: vi.fn() }));
vi.mock("../middleware/uploads", () => ({ validateUploads: (_req: unknown, _res: unknown, next: () => void) => next() }));
vi.mock("../services/dataset", () => ({ extractText: vi.fn(), appendCatalogRow: vi.fn() }));
vi.mock("../middleware/auth", () => ({
  requireAdminAccess: (_req: unknown, _res: unknown, next: () => void) => next(),
  ADM_VER: 2,
  passcodeMatches: vi.fn(),
}));
vi.mock("../middleware/security", () => ({ authLimiter: (_req: unknown, _res: unknown, next: () => void) => next() }));

import { safeRefererPath } from "./admin.routes";

it.each([
  ["https://app.test/admin/pending?page=2", "/admin/pending?page=2"],
  ["https://evil.test/admin", "/admin/pending"],
  ["javascript:alert(1)", "/admin/pending"],
  ["/relative/path", "/admin/pending"],
  [undefined, "/admin/pending"],
])("keeps post-action redirects same-origin: %s", (referer, expected) => {
  expect(safeRefererPath(referer, "/admin/pending")).toBe(expected);
});
