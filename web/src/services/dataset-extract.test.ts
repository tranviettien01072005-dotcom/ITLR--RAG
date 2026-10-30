import { expect, it } from "vitest";
import { extractText } from "./dataset-extract";

it("extracts a valid PDF through the real worker and parser", async () => {
  const stream = "BT /F1 12 Tf 30 100 Td (Isolated fixture Python resource) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, i) => {
    offsets.push(pdf.length);
    pdf += `${i + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += "xref\n0 6\n0000000000 65535 f \n";
  pdf += offsets.slice(1).map(offset => `${String(offset).padStart(10, "0")} 00000 n \n`).join("");
  pdf += `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  await expect(extractText(Buffer.from(pdf), ".pdf")).resolves.toContain("Isolated fixture Python resource");
});
it("fails closed for disabled Office formats", async () => {
  await expect(extractText(Buffer.from("office"), ".docx")).rejects.toThrow("Unsupported");
});
it("rejects corrupt PDFs in the parser worker and frees capacity", async () => {
  for (let n = 0; n < 3; n++) {
    await expect(extractText(Buffer.from("%PDF-1.4\ninvalid\n%%EOF"), ".pdf")).rejects.toThrow();
  }
});
it("classifies malformed PDFs as invalid user documents", async () => {
  await expect(extractText(Buffer.from("%PDF-1.4\ninvalid\n%%EOF"), ".pdf"))
    .rejects.toMatchObject({ name: "DocumentInputError" });
});
