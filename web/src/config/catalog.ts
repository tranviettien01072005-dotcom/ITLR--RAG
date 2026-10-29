// Catalog CSV dùng chung giữa các module (dataset append + đồng bộ Postgres).
// Đường dẫn đúng là var/data/it_learning_items.csv trong repon — KHÔNG phải repo/data
// như trước (sai đường dẫn khiến web tự sinh file rác ở repo/data hoặc crash ENOENT).
// Override khi deploy: env ITEMS_CSV.
import path from "node:path";

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");

export const ITEMS_CSV =
  process.env.ITEMS_CSV || path.join(REPO_ROOT, "var", "data", "web_items.csv");
