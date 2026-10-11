// Названия свои, а не из `Intl`: его вывод («окт.», « г.») различается между движками.
const WEEKDAYS = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];
const MONTHS = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
const MONTHS_FULL = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

const REPEATS: Record<string, string> = {
  DAILY: 'каждый день',
  WEEKLY: 'каждую неделю',
  MONTHLY: 'каждый месяц',
  YEARLY: 'каждый год',
};

/** `2026-10-12` — календарный день без пояса: полдень, чтобы сдвиг пояса не увёл дату. */
function local(date: string): Date {
  return new Date(`${date}T12:00:00`);
}

export function today(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Момент от сервера (`2026-10-11T20:57Z`) — календарным днём там, где его читают. */
export function localDay(moment: string): string {
  const at = new Date(moment);
  if (Number.isNaN(at.getTime())) return moment.slice(0, 10);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`;
}

export const weekday = (date: string): string => WEEKDAYS[local(date).getDay()];
export const dayOfMonth = (date: string): string => String(local(date).getDate());

export function shortDate(date: string): string {
  const day = local(date);
  return `${day.getDate()} ${MONTHS[day.getMonth()]}`;
}

export function fullDate(date: string): string {
  const day = local(date);
  return `${day.getDate()} ${MONTHS_FULL[day.getMonth()]} ${day.getFullYear()}`;
}

/** Простое правило повтора — словами; сложное остаётся как записано. */
export function repeat(rule: string): string {
  const simple = /^FREQ=([A-Z]+)$/.exec(rule);
  return (simple && REPEATS[simple[1]]) ?? rule.replace(/^FREQ=/, '').toLowerCase();
}

/** `facts/2026/10-12.md` → `2026-10-12`. */
export function factDay(path: string): string | null {
  const found = /^facts\/(\d{4})\/(\d{2})-(\d{2})\.md$/.exec(path);
  return found ? `${found[1]}-${found[2]}-${found[3]}` : null;
}

export const stem = (path: string): string => path.slice(path.lastIndexOf('/') + 1).replace(/\.md$/, '');

/** `items/done/2026-10.md` → «окт 2026». */
export function closedMonth(path: string): string {
  const found = /(\d{4}-\d{2})\.md$/.exec(path);
  if (!found) return stem(path);
  const day = local(`${found[1]}-01`);
  return `${MONTHS[day.getMonth()]} ${day.getFullYear()}`;
}

// Заголовки, которые пишет сервер в отображениях.
const HEADINGS: Record<string, string> = {
  inbox: 'Входящие',
  lint: 'Проверка',
  overdue: 'Просрочено',
  'broken links': 'Битые ссылки',
  'pages nothing links to': 'Страницы, на которые никто не ссылается',
};

const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function heading(text: string): string {
  if (HEADINGS[text]) return HEADINGS[text];
  if (DATE.test(text)) return fullDate(text);
  const [from, to] = text.split(' — ');
  return from && to && DATE.test(from) && DATE.test(to) ? `${shortDate(from)} — ${fullDate(to)}` : text;
}

const ORIGINS: Record<string, string> = { said: 'сказано', web: 'с веба', file: 'из файла', forward: 'переслано' };

export const origin = (value: string): string => ORIGINS[value] ?? value;

/** Смещение напоминания ISO 8601 — сколько до момента: `PT10M` → «за 10 мин», `PT0M` → «в срок». */
export function remind(offset: string): string {
  const found = /^-?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/.exec(offset);
  if (!found) return offset;
  const [, weeks, days, hours, minutes] = found;
  const parts = [
    Number(weeks) && `${weeks} нед`,
    Number(days) && `${days} д`,
    Number(hours) && `${hours} ч`,
    Number(minutes) && `${minutes} мин`,
  ].filter(Boolean);
  return parts.length ? `за ${parts.join(' ')}` : 'в срок';
}

/** `pages/people/anna.md` и `people/anna` → `people/anna`. */
export const pageName = (path: string): string => path.replace(/^pages\//, '').replace(/\.md$/, '');
