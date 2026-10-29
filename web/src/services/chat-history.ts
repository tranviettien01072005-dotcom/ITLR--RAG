import { pool, query } from "../db/pool";

export async function ownedChatHistory(userId: number, conversationId?: number) {
  if (!conversationId) return [];
  const own = await query("SELECT 1 FROM conversations WHERE id = $1 AND user_id = $2", [conversationId, userId]);
  if (!own.length) return null;
  const rows = await query<{ role: string; content: string }>(
    "SELECT role, content FROM messages WHERE conversation_id = $1 ORDER BY id DESC LIMIT 20", [conversationId],
  );
  return rows.reverse().filter(row => row.role === "user" || row.role === "assistant");
}

export async function saveChat(userId: number, conversationId: number | undefined, message: string, response: string, metadata: Record<string, unknown> = {}): Promise<number> {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    let id = conversationId;
    if (id) {
      const own = await client.query("SELECT 1 FROM conversations WHERE id = $1 AND user_id = $2 FOR UPDATE", [id, userId]);
      if (!own.rows.length) throw new Error("Conversation unavailable");
    } else {
      const created = await client.query<{ id: number }>("INSERT INTO conversations (user_id, title) VALUES ($1,$2) RETURNING id", [userId, message.slice(0, 60)]);
      id = created.rows[0].id;
    }
    await client.query("INSERT INTO messages (conversation_id, role, content, metadata) VALUES ($1,'user',$2,'{}'::jsonb),($1,'assistant',$3,$4::jsonb)", [id, message, response, JSON.stringify(metadata)]);
    await client.query("UPDATE conversations SET updated_at = now() WHERE id = $1 AND user_id = $2", [id, userId]);
    await client.query("COMMIT");
    return id;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
