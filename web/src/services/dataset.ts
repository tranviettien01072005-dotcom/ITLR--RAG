import { promises as fsp } from "node:fs";
import { ITEMS_CSV } from "../config/catalog";
import { existsSync, readFileSync } from "node:fs";
import { readCatalogColumns } from "./catalog-csv";

export { extractText } from "./dataset-extract";

export function cleanForCsv(text: string, max = 3000): string {
  return (text || "").replace(/\s+/g, " ").trim().slice(0, max);
}

const CSV = ITEMS_CSV;
let catalogWrite = Promise.resolve();

function readLastId(): number {
  if (!existsSync(CSV)) return 0;
  // Use the maximum id, not the last line: merged catalogs are not guaranteed sorted,
  // and reusing an existing id would overwrite a real course row on upsert.
  const lines = readFileSync(CSV, "utf8").trimEnd().split(/\r?\n/);
  let max = 0;
  for (let i = 1; i < lines.length; i++) {
    const n = parseInt(lines[i].split(",")[0], 10);
    if (!Number.isNaN(n) && n > max) max = n;
  }
  return max;
}

function csvField(v: unknown): string {
  const s = v == null ? "" : String(v);
  return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

export interface CatalogRow {
  title: string;
  description: string;
  type?: string;
  level?: string;
  category?: string;
  topics?: string;
  instructor?: string;
  platform?: string;
  link?: string;
}

export async function appendCatalogRow(row: CatalogRow): Promise<number> {
  // shortcut: process-local queue; scale Web beyond one worker only with a shared sequence/lock.
  const write = catalogWrite.then(async () => {
    const columns = await readCatalogColumns(CSV);
    const id = readLastId() + 1;
    const rec: Record<string, unknown> = {
      item_id: id,
      title: row.title || `Tài liệu ${id}`,
      type: row.type || "Tài liệu",
      level: row.level || "",
      description: cleanForCsv(row.description || row.title || ""),
      category: row.category || "Tài liệu cộng đồng",
      topics: row.topics || "",
      instructor: row.instructor || "",
      platform: row.platform || "Tải lên",
      link: row.link || "",
    };
    const line = columns.map((c) => csvField(rec[c])).join(",") + "\n";
    await fsp.appendFile(CSV, line, "utf8");
    return id;
  });
  catalogWrite = write.then(() => undefined, () => undefined);
  return write;
}
