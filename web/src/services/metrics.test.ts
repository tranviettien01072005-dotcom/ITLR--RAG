import { afterEach, expect, it, vi } from "vitest";
import type { NextFunction, Request, Response } from "express";
import { metricsAuthorized, metricsMiddleware, renderMetrics, routeLabel } from "./metrics";

afterEach(() => { delete process.env.METRICS_TOKEN; });

it("labels routes by template, never by concrete id or query", () => {
  const courses = { baseUrl: "", path: "/courses/5129", route: { path: "/courses/:id" } } as unknown as Request;
  const chat = { baseUrl: "", path: "/api/chat/stream", route: { path: "/chat/stream" } } as unknown as Request;
  const missing = { baseUrl: "", path: "/nope", route: undefined } as unknown as Request;
  expect(routeLabel(courses)).toBe("/courses/:id");
  expect(routeLabel(chat)).toBe("/chat/stream");
  expect(routeLabel(missing)).toBe("unmatched");
});

it("records a bounded route label and status class", async () => {
  const listeners: Record<string, () => void> = {};
  const res = {
    statusCode: 200,
    on: (event: string, cb: () => void) => { listeners[event] = cb; },
  } as unknown as Response;
  const next = vi.fn() as unknown as NextFunction;
  metricsMiddleware(
    { baseUrl: "", path: "/courses/5129", method: "GET", route: { path: "/courses/:id" } } as unknown as Request,
    res, next,
  );
  expect(next).toHaveBeenCalled();
  listeners.finish();
  const { body, contentType } = await renderMetrics();
  expect(contentType).toContain("text/plain");
  expect(body).toContain('itlr_web_http_requests_total{route="/courses/:id",method="GET",status_class="2xx"}');
  expect(body).not.toContain("5129");
});

it("allows loopback without a token, and requires the bearer token when configured", () => {
  const loopback = { headers: {}, socket: { remoteAddress: "127.0.0.1" } } as unknown as Request;
  const remote = { headers: {}, socket: { remoteAddress: "203.0.113.5" } } as unknown as Request;
  expect(metricsAuthorized(loopback)).toBe(true);
  expect(metricsAuthorized(remote)).toBe(false);

  process.env.METRICS_TOKEN = "metrics-secret";
  const request = (auth: string) =>
    ({ headers: { authorization: auth }, socket: { remoteAddress: "172.18.0.5" } } as unknown as Request);
  expect(metricsAuthorized(request("Bearer metrics-secret"))).toBe(true);
  expect(metricsAuthorized(request("Bearer wrong"))).toBe(false);
  expect(metricsAuthorized(loopback)).toBe(false);
});
