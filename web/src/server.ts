import { app } from "./app";
import { env } from "./config/env";
import { pool } from "./db/pool";

const server = app.listen(env.port, () => {
  console.log(`[web] listening on port ${env.port}`);
});

let stopping = false;
function shutdown(signal: string): void {
  if (stopping) return;
  stopping = true;
  console.info(`[web] shutdown ${signal}`);
  const deadline = setTimeout(() => {
    console.error("[web] shutdown deadline exceeded");
    process.exit(1);
  }, 25000);
  deadline.unref();
  server.close(() => {
    void pool.end().then(() => {
      clearTimeout(deadline);
    }).catch(() => {
      console.error("[web] database pool shutdown failed");
      process.exitCode = 1;
    });
  });
  // Close SSE and keep-alive connections when the drain deadline expires.
  setTimeout(() => server.closeAllConnections(), 20000).unref();
}
process.once("SIGTERM", () => shutdown("SIGTERM"));
process.once("SIGINT", () => shutdown("SIGINT"));
