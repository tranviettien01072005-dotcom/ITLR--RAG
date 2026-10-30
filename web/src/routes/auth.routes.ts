import { Router } from "express";
import bcrypt from "bcryptjs";
import { z } from "zod";
import { query } from "../db/pool";
import {
  AuthUser,
  signToken,
  setAuthCookie,
  clearAuthCookie,
  requireAuth,
} from "../middleware/auth";
import {
  PASSWORD_RE,
  PASSWORD_HINT,
  RESET_TTL_MINUTES,
  generateResetToken,
  hashResetToken,
  isValidResetTokenFormat,
} from "../services/password";import { sendResetLink } from "../services/mailer";
import { env } from "../config/env";
import { authLimiter } from "../middleware/security";

export const authRouter = Router();

const strongPassword = z.string().regex(PASSWORD_RE, PASSWORD_HINT).max(100);

const registerSchema = z.object({
  name: z.string().trim().min(1, "Vui lòng nhập tên").max(80),
  email: z.string().trim().email("Email không hợp lệ"),
  password: strongPassword,
});

const loginSchema = z.object({
  email: z.string().trim().email("Email không hợp lệ"),
  password: z.string().min(1, "Vui lòng nhập mật khẩu"),
});

function safeNext(raw: unknown): string {
  const n = typeof raw === "string" ? raw : "";
  return n.startsWith("/") && !n.startsWith("//") && !n.includes("\\") ? n : "/dashboard";
}

authRouter.get("/register", (req, res) => {
  if (req.user) return res.redirect("/dashboard");
  res.render("auth/register", { title: "Đăng ký", errors: [], values: {} });
});

authRouter.post("/register", authLimiter, async (req, res) => {
  const parsed = registerSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).render("auth/register", {
      title: "Đăng ký",
      errors: parsed.error.issues.map((i) => i.message),
      values: req.body,
    });
  }
  const { name, email, password } = parsed.data;
  try {
    const hash = await bcrypt.hash(password, 10);
    const rows = await query<AuthUser>(
      "INSERT INTO users (name, email, password_hash) VALUES ($1, $2, $3) RETURNING id, email, name, role",
      [name, email, hash],
    );
    const user = rows[0];
    setAuthCookie(res, signToken(user));
    res.redirect("/dashboard");
  } catch (err: unknown) {
    const dup = (err as { code?: string } | null)?.code === "23505";
    res.status(dup ? 409 : 500).render("auth/register", {
      title: "Đăng ký",
      errors: [dup ? "Email này đã được đăng ký." : "Lỗi hệ thống, thử lại sau."],
      values: req.body,
    });
  }
});

authRouter.get("/login", (req, res) => {
  if (req.user) return res.redirect("/dashboard");
  res.render("auth/login", {
    title: "Đăng nhập",
    errors: [],
    values: {},
    next: req.query.next || "",
  });
});

authRouter.post("/login", authLimiter, async (req, res) => {
  const parsed = loginSchema.safeParse(req.body);
  const nextUrl = safeNext(req.body?.next);
  if (!parsed.success) {
    return res.status(400).render("auth/login", {
      title: "Đăng nhập",
      errors: parsed.error.issues.map((i) => i.message),
      values: req.body,
      next: req.body?.next || "",
    });
  }
  const { email, password } = parsed.data;
  const rows = await query<{
    id: number;
    email: string;
    name: string;
    role: "user" | "admin";
    password_hash: string;
  }>("SELECT id, email, name, role, password_hash FROM users WHERE email = $1", [email]);
  const u = rows[0];
  if (!u || !(await bcrypt.compare(password, u.password_hash))) {
    return res.status(401).render("auth/login", {
      title: "Đăng nhập",
      errors: ["Email hoặc mật khẩu không đúng."],
      values: req.body,
      next: req.body?.next || "",
    });
  }
  setAuthCookie(res, signToken({ id: u.id, email: u.email, name: u.name, role: u.role }));
  res.redirect(nextUrl);
});

authRouter.post("/logout", (req, res) => {
  clearAuthCookie(res);
  res.redirect("/");
});

// ---------------------------------------------------------------------------
// Forgot / reset password — TOKEN-BASED, không bao giờ đổi mật khẩu trực tiếp.
//
// Lỗi cũ (critical, account takeover): POST /forgot đặt luôn password_hash mới và
// khi SMTP lỗi còn in mật khẩu mới ra HTML -> bất kỳ ai biết email của nạn nhân đều
// chiếm tài khoản. Giờ: đặt lại CHỈ được qua token 256-bit; email gửi link (1 lần dùng,
// hết hạn RESET_TTL_MINUTES). Không tiết lộ email nào tồn tại (cùng message mọi nhánh).
// ---------------------------------------------------------------------------

function resetUrl(_req: unknown, token: string): string {
  return `${env.appOrigin}/reset/${token}`;
}

authRouter.get("/forgot", (req, res) => {
  if (req.user) return res.redirect("/account");
  res.render("auth/forgot", {
    title: "Quên mật khẩu",
    error: "",
    done: false,
    email: "",
  });
});

authRouter.post("/forgot", authLimiter, async (req, res) => {
  const email = String(req.body?.email || "").trim();
  const view = (extra: object) =>
    res.render("auth/forgot", {
      title: "Quên mật khẩu",
      error: "",
      done: false,
      email,
      ...extra,
    });

  if (!/^\S+@\S+\.\S+$/.test(email)) return view({ error: "Email không hợp lệ." });

  // Tìm user — kể cả không có, vẫn trả cùng một message (chống dò email tồn tại).
  const rows = await query<{ id: number }>("SELECT id FROM users WHERE email = $1", [email]);

  if (rows.length) {
    const token = generateResetToken();
    const expires = new Date(Date.now() + RESET_TTL_MINUTES * 60 * 1000);
    // Vô hiệu các token cũ còn treo của user này, rồi lưu SHA-256(token) mới.
    await query(
      "UPDATE password_resets SET used_at = now() WHERE user_id = $1 AND used_at IS NULL",
      [rows[0].id],
    );
    await query(
      "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES ($1, $2, $3)",
      [rows[0].id, hashResetToken(token), expires],
    );
    const link = resetUrl(req, token);
    const sent = await sendResetLink(email, link, RESET_TTL_MINUTES).catch(() => false);
    if (!sent || !mailConfigured()) {
      console.warn("[auth] Reset email delivery unavailable; no token logged.");
    }
  }

  view({ done: true });
});

function mailConfigured(): boolean {
  return !!(process.env.SMTP_USER && process.env.SMTP_PASS);
}

// GET form đặt lại: token hợp lệ -> form; hết hạn/đã dùng/sai -> thông báo chung chung.
authRouter.get("/reset/:token", async (req, res) => {
  const render = (valid: boolean, errors: string[] = [], values: object = {}) =>
    res.render("auth/reset", {
      title: valid ? "Đặt lại mật khẩu" : "Link không còn hiệu lực",
      valid,
      token: valid ? req.params.token : "",
      errors,
      values,
      PASSWORD_HINT,
    });

  if (!isValidResetTokenFormat(req.params.token)) return render(false);

  const rows = await query<{ id: number }>(
    "SELECT id FROM password_resets " +
      "WHERE token_hash = $1 AND used_at IS NULL AND expires_at > now() LIMIT 1",
    [hashResetToken(req.params.token)],
  );
  render(rows.length > 0);
});

const resetSchema = z
  .object({
    password: strongPassword,
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Xác nhận mật khẩu không khớp",
    path: ["confirm"],
  });

// POST đặt lại: verify token một lần nữa (tránh TOCTOU giữa GET và POST), đổi mật khẩu,
// đánh dấu token đã dùng và hủy mọi token khác của user đó.
authRouter.post("/reset/:token", authLimiter, async (req, res) => {
  const badLink = () =>
    res.render("auth/reset", {
      title: "Link không còn hiệu lực", valid: false, errors: [], token: "",
      values: {}, PASSWORD_HINT,
    });

  if (!isValidResetTokenFormat(req.params.token)) return badLink();

  const rows = await query<{ user_id: number }>(
    "SELECT user_id FROM password_resets " +
      "WHERE token_hash = $1 AND used_at IS NULL AND expires_at > now() LIMIT 1",
    [hashResetToken(req.params.token)],
  );
  if (!rows.length) return badLink();
  const userId = rows[0].user_id;

  const parsed = resetSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.render("auth/reset", {
      title: "Đặt lại mật khẩu",
      valid: true,
      token: req.params.token,
      errors: parsed.error.issues.map((i) => i.message),
      values: {},
      PASSWORD_HINT,
    });
  }

  const hash = await bcrypt.hash(parsed.data.password, 10);
  const ok = await query<{ id: number }>(
    "UPDATE password_resets SET used_at = now() " +
      "WHERE token_hash = $1 AND used_at IS NULL AND expires_at > now() " +
      "AND user_id = $2 RETURNING id",
    [hashResetToken(req.params.token), userId],
  );
  // Token đã bị người khác dùng trong lúc ta validate (race) -> chặn.
  if (!ok.length) return badLink();
  await query("UPDATE users SET password_hash = $1 WHERE id = $2", [hash, userId]);
  // Hủy các token reset còn lại của user này.
  await query(
    "UPDATE password_resets SET used_at = now() WHERE user_id = $1 AND used_at IS NULL",
    [userId],
  );
  res.redirect("/login");
});

async function hasAvatar(userId: number): Promise<boolean> {
  const r = await query<{ a: boolean }>(
    "SELECT (avatar_data IS NOT NULL) AS a FROM users WHERE id = $1",
    [userId],
  );
  return !!r[0]?.a;
}

authRouter.get("/account", requireAuth, async (req, res) => {
  res.render("account", {
    title: "Tài khoản",
    error: "",
    ok: false,
    hasAvatar: await hasAvatar(req.user!.id),
  });
});

const changeSchema = z
  .object({
    current: z.string().min(1, "Nhập mật khẩu hiện tại"),
    password: strongPassword,
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Xác nhận mật khẩu không khớp",
    path: ["confirm"],
  });

authRouter.post("/account/password", requireAuth, async (req, res) => {
  const av = await hasAvatar(req.user!.id);
  const view = (extra: object) =>
    res.render("account", { title: "Tài khoản", error: "", ok: false, hasAvatar: av, ...extra });
  const parsed = changeSchema.safeParse(req.body);
  if (!parsed.success)
    return view({ error: parsed.error.issues.map((i) => i.message).join(" · ") });

  const rows = await query<{ password_hash: string }>(
    "SELECT password_hash FROM users WHERE id = $1",
    [req.user!.id],
  );
  if (!rows.length || !(await bcrypt.compare(parsed.data.current, rows[0].password_hash))) {
    return view({ error: "Mật khẩu hiện tại không đúng." });
  }
  const hash = await bcrypt.hash(parsed.data.password, 10);
  await query("UPDATE users SET password_hash = $1 WHERE id = $2", [hash, req.user!.id]);
  view({ ok: true });
});
