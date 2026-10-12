import { afterEach, describe, expect, it, vi } from 'vitest';

import { grep, tree } from './api';

/** Сервер, который на любой запрос отвечает одним и тем же телом. */
function answers(body: unknown) {
  const fetcher = vi.fn(async () => new Response(JSON.stringify(body), { status: 200 }));
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

afterEach(() => vi.unstubAllGlobals());

describe('api', () => {
  it('hands the tree over as a list of entries', async () => {
    const entries = [{ path: 'pages', kind: 'dir', description: null }];
    const fetcher = answers({ entries });
    expect(await tree()).toEqual(entries);
    expect(fetcher).toHaveBeenCalledWith('/api/tree?path=&depth=5', expect.anything());
  });

  it('hands the search over as a list of matches', async () => {
    const matches = [{ path: 'pages/people/anna.md', line: 3, text: 'Берлин', before: [], after: [] }];
    const fetcher = answers({ matches });
    expect(await grep('берлин')).toEqual(matches);
    expect(fetcher).toHaveBeenCalledWith('/api/grep?pattern=%D0%B1%D0%B5%D1%80%D0%BB%D0%B8%D0%BD&limit=50', expect.anything());
  });
});
