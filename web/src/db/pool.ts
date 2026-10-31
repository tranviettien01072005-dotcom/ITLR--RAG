import { Pool, type QueryResultRow } from "pg";
import { env } from "../config/env";

export const pool = new Pool({ connectionString: env.databaseUrl });

pool.on("error", (err) => {
  console.error("[pg] lỗi connection nhàn rỗi:", err.message);
});

export async function query<T = QueryResultRow>(text: string, params?: unknown[]): Promise<T[]> {
  const res = await pool.query(text, params);
  return res.rows as T[];
}

export type QueryFn = <T = QueryResultRow>(text: string, params?: unknown[]) => Promise<T[]>;

/**
 * Run a unit of work on one connection. Any throw rolls the whole unit back, so
 * multi-statement writes (token claim + password change) cannot half-apply.
 */
export async function withTransaction<T>(fn: (q: QueryFn) => Promise<T>): Promise<T> {
  const client = await pool.connect();
  const run: QueryFn = async (text, params) => (await client.query(text, params)).rows;
  try {
    await client.query("BEGIN");
    const result = await fn(run);
    await client.query("COMMIT");
    return result;
  } catch (err) {
    await client.query("ROLLBACK").catch(() => {});
    throw err;
  } finally {
    client.release();
  }
}
