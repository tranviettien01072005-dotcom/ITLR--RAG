import { EventEmitter } from 'node:events';
import { afterEach, expect, it, vi } from 'vitest';
import type { Request, Response } from 'express';

const fixture = vi.hoisted(() => ({ friends: vi.fn(), remove: vi.fn() }));
vi.mock('../db/pool', () => ({ query: vi.fn().mockResolvedValue([]) }));
vi.mock('../services/social', () => ({ acceptedFriendIds: fixture.friends }));
vi.mock('../services/realtime', () => ({
  addClient: () => fixture.remove, isOnline: () => false,
  sendToUser: vi.fn(), broadcast: vi.fn(),
}));
import { apiRouter } from './api.routes';

afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });

it('removes a realtime client disconnected while presence lookup is pending', async () => {
  vi.useFakeTimers();
  let resolveFriends!: (ids: number[]) => void;
  fixture.friends.mockReturnValue(new Promise<number[]>(resolve => { resolveFriends = resolve; }));
  const req = Object.assign(new EventEmitter(), { user: { id: 1 } });
  const res = Object.assign(new EventEmitter(), {
    status: vi.fn().mockReturnThis(), set: vi.fn().mockReturnThis(),
    write: vi.fn(), flushHeaders: vi.fn(), destroyed: false,
  });
  const layer = apiRouter.stack.find(layer => layer.route?.path === '/realtime');
  const handler = layer?.route?.stack.at(-1)?.handle;
  if (!handler) throw new Error('Realtime route missing');
  const pending = handler(req as unknown as Request, res as unknown as Response, vi.fn());
  res.destroyed = true;
  res.emit('close');
  req.emit('close');
  resolveFriends([]);
  await pending;
  expect(fixture.remove).toHaveBeenCalledOnce();
  expect(vi.getTimerCount()).toBe(0);
});
