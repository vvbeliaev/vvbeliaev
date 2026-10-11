// Файлы дерева — текст: сервер отдаёт их такими же, какими их читает модель.
// Здесь текст разбирается на блоки, чтобы дела и факты показать строками журнала.

export type Status = 'open' | 'done' | 'cancelled';

const FIELDS = ['at', 'due', 'every', 'remind', 'list', 'page', 'done'] as const;
type Field = (typeof FIELDS)[number];

export type Item = { status: Status; title: string; id: string } & Partial<Record<Field, string>>;

export type Block =
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'day'; date: string }
  | { kind: 'fact'; time: string; id: string; client: string; origin: string }
  | { kind: 'item'; item: Item }
  | { kind: 'text'; text: string };

export type Front = {
  title: string;
  description: string;
  aliases: string[];
  rev: number | null;
  updated: string;
};

const BOX: Record<string, Status> = { ' ': 'open', x: 'done', '-': 'cancelled' };
const FIELD = new RegExp(`^(${FIELDS.join('|')}):(\\S+)$`);
const DAY = /^(\d{4}-\d{2}-\d{2}) [A-Z][a-z]{2}$/;
const FACT = /^(\d{2}:\d{2}) · (\S+) · (.+) · (\S+)$/;

/** Строка элемента: `- [ ] Заголовок  due:2026-10-15  list:shopping  ^t_abc`. Поля идут
 * после заголовка через два пробела; разбор справа, поэтому двойной пробел в заголовке не мешает. */
export function item(line: string): Item | null {
  const head = /^- \[([ x-])\] (.+)$/.exec(line);
  if (!head) return null;
  const parts = head[2].split('  ');
  const last = parts.pop();
  if (!last || !last.startsWith('^') || parts.length === 0) return null;
  const found: Item = { status: BOX[head[1]], title: '', id: last.slice(1) };
  while (parts.length > 1) {
    const field = FIELD.exec(parts[parts.length - 1]);
    if (!field) break;
    found[field[1] as Field] = field[2];
    parts.pop();
  }
  found.title = parts.join('  ');
  return found;
}

/** Отображения, дела и факты: заголовки, строки элементов и куски текста между ними.
 * Страницы сюда не идут: в их теле `#` внутри кода заголовком не является. */
export function blocks(text: string): Block[] {
  const out: Block[] = [];
  let prose: string[] = [];
  const flush = () => {
    if (prose.some((line) => line.trim())) out.push({ kind: 'text', text: prose.join('\n') });
    prose = [];
  };
  for (const line of text.split('\n')) {
    const heading = /^(#{1,6}) (.+)$/.exec(line);
    const parsed = heading ? null : item(line);
    if (!heading && !parsed) {
      prose.push(line);
      continue;
    }
    flush();
    if (parsed) {
      out.push({ kind: 'item', item: parsed });
      continue;
    }
    const [, marks, title] = heading as RegExpExecArray;
    const day = marks.length === 2 ? DAY.exec(title) : null;
    const fact = marks.length === 2 ? FACT.exec(title) : null;
    if (day) out.push({ kind: 'day', date: day[1] });
    else if (fact) out.push({ kind: 'fact', time: fact[1], id: fact[2], client: fact[3], origin: fact[4] });
    else out.push({ kind: 'heading', level: marks.length, text: title });
  }
  flush();
  return out;
}

/** Шапка страницы, которую пишет сервер: значения в ней — JSON. */
export function frontmatter(text: string): { front: Front | null; body: string } {
  const end = text.startsWith('---\n') ? text.indexOf('\n---\n', 3) : -1;
  if (end < 0) return { front: null, body: text };
  const fields = new Map<string, string>();
  for (const line of text.slice(4, end).split('\n')) {
    const colon = line.indexOf(': ');
    if (colon > 0) fields.set(line.slice(0, colon), line.slice(colon + 2));
  }
  const json = <T>(key: string, fallback: T): T => {
    try {
      return JSON.parse(fields.get(key) ?? '') as T;
    } catch {
      return fallback;
    }
  };
  return {
    front: {
      title: json('title', ''),
      description: json('description', ''),
      aliases: json<string[]>('aliases', []),
      rev: Number(fields.get('rev')) || null,
      updated: fields.get('updated') ?? '',
    },
    body: text.slice(end + 5).replace(/^\n/, ''),
  };
}
