import { Worker } from "node:worker_threads";

let active = 0;
// Untrusted document parsers run off the event loop with bounded memory and time.
export async function extractText(buf: Buffer, ext: string): Promise<string> {
  if (active >= 2) throw new Error("Document extraction is busy; retry later");
  const packages: Record<string, string> = { ".pdf": "pdf-parse/lib/pdf-parse.js" };
  const pkg = packages[ext];
  if (!pkg) throw new Error("Unsupported document format");
  active++;
  try {
    return await new Promise<string>((resolve, reject) => {
      const worker = new Worker(`
        const { parentPort, workerData } = require('node:worker_threads');
        (async () => {
          const parser = require(workerData.module), b = Buffer.from(workerData.buffer);
          const text = (await parser(b, { max: 100 })).text;
          parentPort.postMessage(String(text || '').slice(0, 100000));
        })().catch(e => { throw e; });
      `, { eval: true, workerData: { module: require.resolve(pkg), buffer: buf, ext }, resourceLimits: { maxOldGenerationSizeMb: 128, maxYoungGenerationSizeMb: 16 } });
      const timer = setTimeout(() => { void worker.terminate(); reject(new Error("Document extraction timed out")); }, 5000);
      worker.once("message", text => { clearTimeout(timer); void worker.terminate(); resolve(text); });
      worker.once("error", error => { clearTimeout(timer); reject(error); });
      worker.once("exit", code => { clearTimeout(timer); if (code !== 0) reject(new Error("Document extraction failed")); });
    });
  } finally { active--; }
}
