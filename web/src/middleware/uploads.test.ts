import { expect, it } from "vitest";
import { inspectUpload, validateUploads } from "./uploads";
const file = (name: string, mime: string, data: Buffer) => ({ originalname: name, mimetype: mime, buffer: data, size: data.length }) as Express.Multer.File;
it("rejects HTML disguised as a PNG", () => {
  expect(() => inspectUpload(file("photo.png", "image/png", Buffer.from("<script>alert(1)</script>")))).toThrow();
});
it("rejects MIME mismatches", () => {
  expect(() => inspectUpload(file("image.png", "text/html", Buffer.from("89504e470d0a1a0a", "hex")))).toThrow();
});
it("identifies PNG from bytes rather than client headers", () => {
  const png = Buffer.alloc(33); Buffer.from("89504e470d0a1a0a", "hex").copy(png); png.write("IHDR", 12); png.writeUInt32BE(10, 16); png.writeUInt32BE(10, 20);
  expect(inspectUpload(file("image.png", "image/png", png))).toBe("image/png");
});
it("quarantines invalid files before invoking the route", () => {
  const req = { file: file("bad.pdf", "application/pdf", Buffer.from("html")) };
  let status = 0, next = false;
  const res = { status(n: number) { status = n; return this; }, json() {} };
  validateUploads(req as never, res as never, (() => { next = true; }) as never);
  expect(status).toBe(415); expect(next).toBe(false); expect(req.file).toBeUndefined();
});
it("rejects oversized Office entries before inflation", () => {
  const zip = Buffer.alloc(31); zip.writeUInt32LE(0x04034b50, 0); zip.writeUInt32LE(30_000_000, 22);
  expect(() => inspectUpload(file("bomb.docx", "application/octet-stream", zip))).toThrow();
});
it("rejects legacy Office and active SVG formats", () => {
  expect(() => inspectUpload(file("macro.xls", "application/vnd.ms-excel", Buffer.from("d0cf11e0a1b11ae1", "hex")))).toThrow();
  expect(() => inspectUpload(file("avatar.svg", "image/svg+xml", Buffer.from("<svg onload='alert(1)'/>")))).toThrow();
});
