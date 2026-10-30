import { createReadStream, existsSync } from "node:fs";
import { pipeline } from "node:stream/promises";
import { from as copyFrom } from "pg-copy-streams";
import { pool } from "./pool";
import { ITEMS_CSV } from "../config/catalog";
import { PROVENANCE_COLUMNS, readCatalogColumns } from "../services/catalog-csv";

export async function syncCourses(csv = ITEMS_CSV) {
  if (!existsSync(csv)) throw new Error("Catalog missing; run export_web_catalog.py first");
  const columns = await readCatalogColumns(csv);
  const header = columns.join(",");
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query("CREATE TEMP TABLE courses_stage (LIKE courses INCLUDING DEFAULTS) ON COMMIT DROP");
    const preserveEmpty = columns.includes("origin") ? `, FORCE_NOT_NULL (${PROVENANCE_COLUMNS})` : "";
    await pipeline(createReadStream(csv), client.query(copyFrom(`COPY courses_stage (${header}) FROM STDIN WITH (FORMAT csv, HEADER true${preserveEmpty})`)));
    const updates = columns.filter(c => c !== "item_id").map(c => `${c}=EXCLUDED.${c}`).join(",");
    const result = await client.query(`INSERT INTO courses (${header}) SELECT ${header} FROM courses_stage WHERE true ON CONFLICT (item_id) DO UPDATE SET ${updates}`);
    await client.query("COMMIT");
    console.log(`[sync] Imported ${result.rowCount} resources; existing enrollments preserved`);
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally { client.release(); }
}

if (require.main === module) {
  syncCourses().catch(error => { console.error("[sync]", error.message); process.exitCode = 1; }).finally(() => pool.end());
}
