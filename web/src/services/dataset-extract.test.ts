import { expect, it } from "vitest";
import { extractText } from "./dataset-extract";
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
