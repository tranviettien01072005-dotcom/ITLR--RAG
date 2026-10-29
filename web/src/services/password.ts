import crypto from "node:crypto";

export const PASSWORD_RE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*[^A-Za-z0-9]).{8,}$/;
export const PASSWORD_HINT =
  "Mật khẩu tối thiểu 8 ký tự, có chữ HOA, chữ thường và ký tự đặc biệt.";

export function isStrongPassword(p: string): boolean {
  return PASSWORD_RE.test(p);
}

const LOWER = "abcdefghijkmnpqrstuvwxyz";
const UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ";
const DIGIT = "23456789";
const SPECIAL = "!@#$%^&*-_=+?";

function pick(set: string): string {
  return set[crypto.randomInt(set.length)];
}

export function generatePassword(len = 10): string {
  len = Math.max(8, len);
  const all = LOWER + UPPER + DIGIT + SPECIAL;
  const chars = [pick(LOWER), pick(UPPER), pick(SPECIAL), pick(DIGIT)];
  while (chars.length < len) chars.push(pick(all));
  for (let i = chars.length - 1; i > 0; i--) {
    const j = crypto.randomInt(i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }
  return chars.join("");
}

// ---------------------------------------------------------------------------
// Reset-password token flow (thay cho "tạo mật khẩu mới gửi qua email" trước đây):
//  - Token 256-bit random, CHỈ gửi qua email dạng link một lần.
//  - DB chỉ lưu SHA-256(token) + expiry; rò rỉ DB/fallback log không lộ token dùng được.
//  - TTL ngắn mặc định 15 phút; đã dùng -> vô hiệu.
//  - E-mail chưa từng đổi mật khẩu nào thông qua POST /forgot.
// ---------------------------------------------------------------------------

export const RESET_TTL_MINUTES = Math.max(
  1,
  parseInt(process.env.RESET_TOKEN_TTL_MINUTES || "15", 10) || 15,
);

export function generateResetToken(): string {
  return crypto.randomBytes(32).toString("hex");
}

export function hashResetToken(token: string): string {
  return crypto.createHash("sha256").update(token).digest("hex");
}

export function isValidResetTokenFormat(token: unknown): token is string {
  return typeof token === "string" && /^[0-9a-f]{64}$/.test(token);
}
