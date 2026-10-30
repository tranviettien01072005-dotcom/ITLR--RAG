import { expect, it, vi } from 'vitest';
const mocks = vi.hoisted(() => ({ query: vi.fn().mockResolvedValue([{ id: 1 }]), append: vi.fn() }));
vi.mock('../db/pool', () => ({ query: mocks.query }));
vi.mock('../services/dataset', async () => ({
  ...await vi.importActual('../services/dataset'), appendCatalogRow: mocks.append,
}));
import { apiRouter } from './api.routes';
it('rejects corrupt post PDF before inserting a post or appending catalog', async () => {
  const handler = apiRouter.stack.find(layer => layer.route?.path === '/posts')?.route?.stack.at(-1)?.handle;
  if (!handler) throw new Error('Post route missing');
  const req = { body: { content: 'fixture' }, user: { id: 1, name: 'Fixture' }, files: {
    doc: [{ buffer: Buffer.from('%PDF-1.4\ninvalid\n%%EOF'), originalname: 'fixture.pdf', mimetype: 'application/pdf' }],
  } };
  await expect(handler(req as never, {} as never, vi.fn())).rejects.toThrow();
  expect(mocks.query).not.toHaveBeenCalled();
  expect(mocks.append).not.toHaveBeenCalled();
});
