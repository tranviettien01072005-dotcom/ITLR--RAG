import path from "node:path";
import type { Request, Response, NextFunction } from "express";

// Files stay in request memory (not public storage) until every file passes.
export function inspectUpload(file: Express.Multer.File): string {
  const b = file.buffer;
  const ext = path.extname(file.originalname).toLowerCase();
  const invalid = () => { throw new Error("File signature, MIME or resource limit is invalid"); };
  if (!b.length || b.length > 20 * 1024 * 1024) return invalid();
  let mime = "";
  if ([".png"].includes(ext) && b.length >= 33 && b.subarray(0, 8).equals(Buffer.from("89504e470d0a1a0a", "hex")) && b.toString("ascii", 12, 16) === "IHDR") {
    if (!b.readUInt32BE(16) || !b.readUInt32BE(20) || b.readUInt32BE(16) * b.readUInt32BE(20) > 25_000_000) return invalid();
    mime = "image/png";
  } else if ([".jpg", ".jpeg"].includes(ext) && b.length > 4 && b[0] === 255 && b[1] === 216 && b[2] === 255 && b[b.length - 2] === 255 && b[b.length - 1] === 217) mime = "image/jpeg";
  else if (ext === ".gif" && b.length >= 13 && /^GIF8[79]a$/.test(b.toString("ascii", 0, 6))) {
    if (!b.readUInt16LE(6) || !b.readUInt16LE(8) || b.readUInt16LE(6) * b.readUInt16LE(8) > 25_000_000) return invalid();
    mime = "image/gif";
  } else if (ext === ".webp" && b.length >= 20 && b.toString("ascii", 0, 4) === "RIFF" && b.toString("ascii", 8, 12) === "WEBP" && b.readUInt32LE(4) + 8 === b.length) mime = "image/webp";
  else if (ext === ".pdf" && b.subarray(0, 5).toString() === "%PDF-" && b.subarray(-1024).includes(Buffer.from("%%EOF"))) mime = "application/pdf";
  if (!mime || (file.mimetype !== mime && file.mimetype !== "application/octet-stream")) return invalid();
  return mime;
}

export function validateUploads(req: Request, res: Response, next: NextFunction): void {
  const files = [ ...(req.file ? [req.file] : []), ...Object.values(req.files || {}).flat() ] as Express.Multer.File[];
  try {
    if (files.reduce((sum, file) => sum + file.size, 0) > 20 * 1024 * 1024) throw new Error("Upload too large");
    files.forEach(file => { file.mimetype = inspectUpload(file); });
    next();
  } catch {
    files.forEach(file => file.buffer.fill(0));
    req.file = undefined; req.files = undefined;
    res.status(415).json({ error: "File không hợp lệ. Chỉ nhận ảnh raster hoặc PDF đã kiểm tra (tổng ≤ 20MB); không nhận video hay Office." });
  }
}
