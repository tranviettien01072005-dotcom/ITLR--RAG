import { afterAll, beforeAll, expect, it, vi } from "vitest";
import type { Server } from "node:http";
import type { AddressInfo } from "node:net";

const database = vi.hoisted(() => ({ query: vi.fn() }));
vi.mock("./db/pool", () => ({ query: database.query }));
import { app } from "./app";

let server: Server;
let origin: string;
beforeAll(async () => {
  await new Promise<void>(resolve => { server = app.listen(0, "127.0.0.1", resolve); });
  origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(async () => {
  server.closeAllConnections();
  await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
});

it("serves liveness without touching PostgreSQL or authentication", async () => {
  database.query.mockClear();
  const response = await fetch(`${origin}/health`);
  expect(response.status).toBe(200);
  expect(await response.json()).toEqual({ status: "ok" });
  expect(response.headers.get("x-content-type-options")).toBe("nosniff");
  expect(database.query).not.toHaveBeenCalled();
});

it("reports database readiness and fails closed when PostgreSQL is unavailable", async () => {
  database.query.mockResolvedValueOnce([]).mockRejectedValueOnce(new Error("offline"));
  expect((await fetch(`${origin}/ready`)).status).toBe(200);
  const response = await fetch(`${origin}/ready`);
  expect(response.status).toBe(503);
  expect(await response.json()).toEqual({ status: "unavailable" });
  expect(database.query).toHaveBeenCalledWith("SELECT 1");
});
