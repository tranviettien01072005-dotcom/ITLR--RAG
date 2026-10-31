import crypto from "node:crypto";
import type { NextFunction, Request, Response } from "express";
import client from "prom-client";

/** Low-cardinality Web metrics: route templates only, never query text or user data. */
export const registry = new client.Registry();
client.collectDefaultMetrics({ register: registry, prefix: "itlr_web_" });

const httpRequests = new client.Counter({
  name: "itlr_web_http_requests_total",
  help: "HTTP requests by route template, method and status class",
  labelNames: ["route", "method", "status_class"],
  registers: [registry],
});
const httpDuration = new client.Histogram({
  name: "itlr_web_http_request_duration_seconds",
  help: "HTTP request duration",
  labelNames: ["route", "method"],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60],
  registers: [registry],
});
const chatStreams = new client.Counter({
  name: "itlr_web_chat_streams_total",
  help: "SSE chat stream outcomes handled by Web",
  labelNames: ["result"],
  registers: [registry],
});

export function routeLabel(req: Request): string {
  if (req.route?.path) return `${req.baseUrl || ""}${req.route.path}`;
  const path = req.path || "";
  if (path.startsWith("/api/")) return "api";
  return "unmatched";
}

export function metricsMiddleware(req: Request, res: Response, next: NextFunction): void {
  const started = process.hrtime.bigint();
  res.on("finish", () => {
    const seconds = Number(process.hrtime.bigint() - started) / 1e9;
    const route = routeLabel(req);
    httpRequests.inc({ route, method: req.method, status_class: `${Math.floor(res.statusCode / 100)}xx` });
    httpDuration.observe({ route, method: req.method }, seconds);
  });
  next();
}

export function observeChatStream(result: "done" | "error" | "aborted"): void {
  chatStreams.inc({ result });
}

function secureEqual(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}

/** Bearer token when METRICS_TOKEN is set; otherwise loopback only (local dev). */
export function metricsAuthorized(req: Request): boolean {
  const expected = process.env.METRICS_TOKEN || "";
  if (expected) {
    const header = req.headers.authorization || "";
    const given = header.startsWith("Bearer ") ? header.slice(7) : "";
    return secureEqual(given, expected);
  }
  const remote = req.socket?.remoteAddress || "";
  return ["127.0.0.1", "::1", "::ffff:127.0.0.1"].includes(remote);
}

export async function renderMetrics(): Promise<{ body: string; contentType: string }> {
  return { body: await registry.metrics(), contentType: registry.contentType };
}
