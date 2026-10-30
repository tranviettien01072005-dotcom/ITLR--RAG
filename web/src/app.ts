import path from "node:path";
import { DocumentInputError } from "./services/dataset-extract";
import "express-async-errors";
import express, { NextFunction, Request, Response } from "express";
import cookieParser from "cookie-parser";
import { env } from "./config/env";
import { query } from "./db/pool";
import { loadUser } from "./middleware/auth";
import { securityHeaders, csrfProtection, globalLimiter } from "./middleware/security";
import { authRouter } from "./routes/auth.routes";
import { pagesRouter } from "./routes/pages.routes";
import { apiRouter } from "./routes/api.routes";
import { adminRouter } from "./routes/admin.routes";
import { socialRouter } from "./routes/social.routes";
import { learningRouter } from "./routes/learning.routes";

export const app = express();
app.disable("x-powered-by");
app.locals.ASSET_VER = Date.now();
app.set("trust proxy", env.trustedProxies.length ? env.trustedProxies : false);

app.use(securityHeaders);

app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));
app.use(express.static(path.join(__dirname, "public"), { maxAge: env.isProd ? "7d" : "1h" }));

app.use(express.urlencoded({ extended: true, limit: "1mb" }));
app.use(express.json({ limit: "1mb" }));
app.use(cookieParser());

app.use(globalLimiter);

app.get("/health", (_req, res) => res.json({ status: "ok" }));
app.get("/ready", async (_req, res) => {
  try { await query("SELECT 1"); res.json({ status: "ready" }); }
  catch { res.status(503).json({ status: "unavailable" }); }
});

app.use(loadUser);

app.use(csrfProtection);

const PUBLIC_PATHS = new Set(["/login", "/register", "/logout", "/forgot"]);
app.use((req: Request, res: Response, next: NextFunction) => {
  if (req.user || PUBLIC_PATHS.has(req.path) || req.path.startsWith("/reset") || req.path.startsWith("/admin"))
    return next();
  if (req.path.startsWith("/api/")) {
    res.status(401).json({ error: "Cần đăng nhập." });
    return;
  }
  res.redirect("/login?next=" + encodeURIComponent(req.originalUrl));
});

app.use("/", authRouter);
app.use("/", learningRouter);
app.use("/", socialRouter);
app.use("/", pagesRouter);
app.use("/admin", adminRouter);
app.use("/api", apiRouter);

app.use((req: Request, res: Response) => {
  res.status(404).render("error", { title: "404", message: "Không tìm thấy trang: " + req.path });
});

app.use((err: unknown, _req: Request, res: Response, _next: NextFunction) => {
  if (err instanceof DocumentInputError && !res.headersSent) {
    res.status(400).json({ error: err.message });
    return;
  }
  console.error("[error]", err instanceof Error ? err.message : String(err));
  if (res.headersSent) return;
  res.status(500).render("error", { title: "Lỗi", message: "Đã có lỗi xảy ra phía máy chủ." });
});
