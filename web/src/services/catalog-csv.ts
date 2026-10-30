import { createReadStream } from "node:fs";
import { createInterface } from "node:readline";

export const BASE_COLUMNS = "item_id,title,type,level,description,category,topics,instructor,platform,link";
export const PROVENANCE_COLUMNS = "origin,crawl_license,crawl_lang,crawl_hash,source_updated_at,source_fetched_at";

/** Whitelist columns before constructing COPY SQL or appending a catalog record. */
export async function readCatalogColumns(csv: string): Promise<string[]> {
  const input = createReadStream(csv);
  const reader = createInterface({ input, crlfDelay: Infinity });
  try {
    for await (const header of reader) {
      if (![BASE_COLUMNS, `${BASE_COLUMNS},${PROVENANCE_COLUMNS}`].includes(header)) break;
      return header.split(",");
    }
    throw new Error("Unsupported catalog CSV columns");
  } finally {
    reader.close();
    input.destroy();
  }
}
