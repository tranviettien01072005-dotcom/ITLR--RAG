import type { Request, Response } from "express";

/**
 * Serve a buffer with single-range semantics. Unsupported units, malformed or
 * multipart ranges fall back to the full 200 response; unsatisfiable ranges 416.
 * Suffixes larger than the payload return the full representation.
 */
export function sendBufferWithRange(
  req: Request,
  res: Response,
  buf: Buffer,
  mime: string,
): void {
  const total = buf.length;
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("Content-Security-Policy", "sandbox; default-src 'none'");
  res.setHeader("Cache-Control", "private, no-store");
  res.setHeader("Content-Type", mime);
  res.setHeader("Accept-Ranges", "bytes");

  const range = req.headers.range;
  const suffix = /^bytes=-(\d+)$/.exec(range || "");
  const ranges = range?.startsWith("bytes=") ? req.range(total) : undefined;
  // range-parser rejects suffixes larger than the representation.
  if (suffix && Number(suffix[1]) >= total && total > 0) {
    res.status(206).setHeader("Content-Range", `bytes 0-${total - 1}/${total}`);
    res.setHeader("Content-Length", total);
    res.end(buf);
    return;
  }
  if (ranges === -1) {
    res.status(416).setHeader("Content-Range", `bytes */${total}`);
    res.end();
    return;
  }
  if (Array.isArray(ranges) && ranges.type === "bytes" && ranges.length === 1) {
    const { start, end } = ranges[0];
    res.status(206);
    res.setHeader("Content-Range", `bytes ${start}-${end}/${total}`);
    res.setHeader("Content-Length", end - start + 1);
    res.end(buf.subarray(start, end + 1));
    return;
  }
  res.setHeader("Content-Length", total);
  res.end(buf);
}
