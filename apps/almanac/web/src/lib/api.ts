// Только чтение: сайт показывает то, что записано, и ничего не меняет.

export type Entry = { path: string; kind: 'dir' | 'file'; description: string | null };

export type FileView = {
  path: string;
  text: string;
  rev: number | null;
  backlinks: string[] | null;
  // Открытые дела страницы строками, как их печатает сервер; у всего, что не текущая страница, — null.
  items: string[] | null;
  writable: boolean;
};

export type Match = { path: string; line: number; text: string; before: string[]; after: string[] };

async function get<T>(name: string, params: Record<string, string | number>): Promise<T> {
  const query = new URLSearchParams(Object.entries(params).map(([key, value]) => [key, String(value)]));
  const response = await fetch(`/api/${name}?${query}`, { headers: { accept: 'application/json' } });
  if (response.status === 401) {
    location.assign('/login?next=/');
    throw new Error('Нужен вход');
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null;
    throw new Error(typeof detail === 'string' ? detail : `Сервер ответил ${response.status}`);
  }
  return (await response.json()) as T;
}

// Сервер отвечает объектом с названным списком (`entries`, `matches`); сайту список нужен сам по себе.
export const tree = async (): Promise<Entry[]> =>
  (await get<{ entries: Entry[] }>('tree', { path: '', depth: 5 })).entries;
export const file = (path: string): Promise<FileView> => get('file', { path });
export const grep = async (pattern: string): Promise<Match[]> =>
  (await get<{ matches: Match[] }>('grep', { pattern, limit: 50 })).matches;
