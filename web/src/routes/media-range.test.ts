import { afterAll, beforeAll, expect, it, vi } from 'vitest';
import express, { type Request, type Response, type NextFunction } from 'express';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';

const database = vi.hoisted(() => ({ query: vi.fn() }));
vi.mock('../db/pool', () => ({ query: database.query }));
vi.mock('../middleware/auth', () => ({
  requireAuth: (req: Request, _res: Response, next: NextFunction) => {
    req.user = { id: 1, email: 'fixture@example.org', name: 'Fixture', role: 'user' };
    next();
  },
  signToken: vi.fn(),
  setAuthCookie: vi.fn(),
}));
import { apiRouter } from './api.routes';
import { socialRouter } from './social.routes';

let server: Server;
let origin: string;
beforeAll(async () => {
  const app = express();
  app.use('/api', apiRouter);
  app.use(socialRouter);
  await new Promise<void>(resolve => { server = app.listen(0, '127.0.0.1', resolve); });
  origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(async () => {
  server.closeAllConnections();
  await new Promise<void>((resolve, reject) => server.close(err => err ? reject(err) : resolve()));
});

it.each(['/api/media/post/1/video', '/api/messages/media/1/video'])(
  'clamps oversized range end to actual bytes at %s', async path => {
    const bytes = Buffer.from('fixture-video');
    database.query.mockResolvedValueOnce([{
      video_data: bytes, video_mime: 'video/mp4', data: bytes, mime: 'video/mp4',
      sender_id: 1, recipient_id: 2,
    }]);
    const response = await fetch(origin + path, {
      headers: { Range: 'bytes=0-999999' }, signal: AbortSignal.timeout(3000),
    });
    try {
      expect(response.status).toBe(206);
      expect(response.headers.get('content-range')).toBe(`bytes 0-${bytes.length - 1}/${bytes.length}`);
      expect(Number(response.headers.get('content-length'))).toBe(bytes.length);
      expect(Buffer.from(await response.arrayBuffer())).toEqual(bytes);
    } finally {
      if (!response.bodyUsed) await response.body?.cancel();
    }
  });

it.each(['/api/media/post/1/video', '/api/messages/media/1/video'].flatMap(path =>
  [
    { range: 'bytes=-5', status: 206, body: 'video' },
    { range: 'bytes=-999', status: 206, body: 'fixture-video' },
    { range: 'widgets=99-', status: 200, body: 'fixture-video' },
    { range: 'bytes=8-', status: 206, body: 'video' },
    { range: 'bytes=99-', status: 416, body: '' },
    { range: 'bytes=-0', status: 416, body: '' },
    { range: 'invalid', status: 200, body: 'fixture-video' },
    { range: 'bytes=0-1,5-6', status: 200, body: 'fixture-video' },
  ].map(test => ({ path, ...test }))
))('handles $range at $path', async ({ path, range, status, body }) => {
  const bytes = Buffer.from('fixture-video');
  database.query.mockResolvedValueOnce([{
    video_data: bytes, video_mime: 'video/mp4', data: bytes, mime: 'video/mp4',
    sender_id: 1, recipient_id: 2,
  }]);
  const response = await fetch(origin + path, {
    headers: { Range: range }, signal: AbortSignal.timeout(3000),
  });
  expect(response.status).toBe(status);
  expect(await response.text()).toBe(body);
});
