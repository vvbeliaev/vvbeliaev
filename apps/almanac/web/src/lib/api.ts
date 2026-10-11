// Только чтение: сайт показывает то, что записано, и ничего не меняет.

export type Entry = { path: string; kind: 'dir' | 'file'; description: string | null };

export type FileView = {
  path: string;
  text: string;
  rev: number | null;
  backlinks: string[] | null;
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

export const tree = (): Promise<Entry[]> => get('tree', { path: '', depth: 5 });
export const file = (path: string): Promise<FileView> => get('file', { path });
export const grep = (pattern: string): Promise<Match[]> => get('grep', { pattern, limit: 50 });
