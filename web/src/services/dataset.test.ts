import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const state = vi.hoisted(() => ({ csv: "" }));
vi.mock("../config/catalog", () => ({ get ITEMS_CSV() { return state.csv; } }));

const base = "item_id,title,type,level,description,category,topics,instructor,platform,link";
const provenance = "origin,crawl_license,crawl_lang,crawl_hash,source_updated_at,source_fetched_at";
let directory: string;

beforeEach(() => {
  vi.resetModules();
  directory = mkdtempSync(path.join(tmpdir(), "itlr-catalog-test-"));
  state.csv = path.join(directory, "catalog.csv");
});
afterEach(() => rmSync(directory, { recursive: true, force: true }));

it.each([base, `${base},${provenance}`])("appends rows matching the existing catalog header %s", async header => {
  writeFileSync(state.csv, `${header}\n`);
  const { appendCatalogRow } = await import("./dataset");
  await expect(appendCatalogRow({ title: "Python", description: "Practice" })).resolves.toBe(1);
  const row = readFileSync(state.csv, "utf8").trimEnd().split("\n")[1];
  expect(row.split(",")).toHaveLength(header.split(",").length);
});

it("rejects an unknown header without appending data", async () => {
  const original = "item_id,title,unknown\n";
  writeFileSync(state.csv, original);
  const { appendCatalogRow } = await import("./dataset");
  await expect(appendCatalogRow({ title: "Python", description: "Practice" })).rejects.toThrow("Unsupported catalog CSV columns");
  expect(readFileSync(state.csv, "utf8")).toBe(original);
});
