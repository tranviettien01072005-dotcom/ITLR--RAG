import dotenv from "dotenv";

dotenv.config();

function required(name: string, fallback?: string): string {
  const v = process.env[name] ?? fallback;
  if (v === undefined || v === "") {
    throw new Error(`Thiếu biến môi trường ${name}. Hãy tạo web/.env từ .env.example.`);
  }
  return v;
}

const isProd = process.env.NODE_ENV === "production";

const jwtSecret = required("JWT_SECRET");
if (jwtSecret.length < 32 || /dev-secret|doi-thanh|change.me/i.test(jwtSecret)) {
  throw new Error("JWT_SECRET phải là secret riêng dài ít nhất 32 ký tự.");
}
const adminPasscode = required("ADMIN_PASSCODE");
if (adminPasscode.length < 16 || /change.me|doi-thanh/i.test(adminPasscode)) {
  throw new Error("ADMIN_PASSCODE phải là secret riêng dài ít nhất 16 ký tự.");
}
const databaseUrl = required("DATABASE_URL");
const db = new URL(databaseUrl);
if (!["postgres:", "postgresql:"].includes(db.protocol) || !db.password ||
    ["postgres", "password", "changeme"].includes(decodeURIComponent(db.password).toLowerCase())) {
  throw new Error("DATABASE_URL phải dùng credentials riêng, không dùng mật khẩu mặc định.");
}
// In-memory rate limiting and presence require exactly one Node process.
for (const name of ["WEB_CONCURRENCY", "NODE_APP_INSTANCE", "PM2_INSTANCES"]) {
  const value = process.env[name];
  if (value && value !== (name === "NODE_APP_INSTANCE" ? "0" : "1")) {
    throw new Error(`${name}: web requires one worker; use a shared limiter before scaling.`);
  }
}
const trustedProxies = (process.env.TRUSTED_PROXIES || "").split(",").map(v => v.trim()).filter(Boolean);

export const env = {
  port: parseInt(process.env.PORT || "3000", 10),
  databaseUrl,
  trustedProxies,
  jwtSecret,
  recommenderUrl: (process.env.RECOMMENDER_URL || "http://localhost:8000").replace(/\/$/, ""),
  adminPasscode,
  isProd,
  // Origin tuyệt đối để dựng link trong email (reset mật khẩu...). KHÔNG lấy Host header
  // của request: host bị giả trong mail = kẻ tấn công chiếm token khi nạn nhân bấm link.
  appOrigin: (process.env.APP_ORIGIN || "http://localhost:3000").replace(/\/$/, ""),
};

if (env.isProd) {
  if (!process.env.APP_ORIGIN || new URL(env.appOrigin).protocol !== "https:") {
    throw new Error("APP_ORIGIN must be an explicit HTTPS origin in production.");
  }
}
