import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";

it("EJS views avoid javascript: URLs blocked by the CSP", () => {
  const root = resolve("src/views");
  const offenders = (readdirSync(root, { recursive: true }) as string[])
    .filter((name) => name.endsWith(".ejs"))
    .filter((name) =>
      /href\s*=\s*["']?\s*javascript:/i.test(readFileSync(resolve(root, name), "utf8")),
    );
  expect(offenders).toEqual([]);
});
