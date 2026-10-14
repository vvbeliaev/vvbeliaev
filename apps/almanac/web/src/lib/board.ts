// Доска — страница `pages/boards/…`: принципы одной области, собранные, чтобы смотреть на них вместе.
// Её тело — обычный Markdown, который пишет модель; здесь он разбирается на карточки и напряжения.

export type Card = { target: string; note: string };
export type Tension = { targets: string[]; note: string };

export type BoardBlock =
  | { kind: 'prose'; text: string }
  | { kind: 'cards'; cards: Card[] }
  | { kind: 'tensions'; tensions: Tension[] };

export type BoardSection = { title: string | null; blocks: BoardBlock[] };

// Та же ссылка, что в `markdown.ts`: `[[principles/slug]]` или `[[principles/slug|подпись]]`.
const LINK = /\[\[([a-z0-9-]+\/[a-z0-9-]+)(?:\|[^\]\n]{0,120})?\]\]/g;
const BULLET = /^\s*[-*] /;
const SECTION = /^## (.+)$/;
// Случай в теле принципа — пункт списка, который начинается с месяца: `- 2026-10 — что было`.
const CASE = /^\s*[-*] (\d{4}-\d{2})\b/;

/** Комментарий строки доски: то, что идёт после ` — ` за ссылками. */
function noteOf(line: string): string {
  const rest = line.replace(BULLET, '').replace(LINK, '');
  const dash = rest.indexOf('—');
  return (dash >= 0 ? rest.slice(dash + 1) : rest).replace(/^[\s,;:/·⟷↔–-]+/, '').trim();
}

/** Разделы доски по `##`. Пункт списка с одной ссылкой — карточка, с двумя и больше — напряжение
 * между ними, всё остальное — текст как есть. Соседние строки одного вида собираются в один блок. */
export function board(body: string): BoardSection[] {
  const sections: BoardSection[] = [{ title: null, blocks: [] }];
  let prose: string[] = [];
  const current = (): BoardSection => sections[sections.length - 1];
  const flush = (): void => {
    if (prose.some((line) => line.trim())) current().blocks.push({ kind: 'prose', text: prose.join('\n') });
    prose = [];
  };
  const last = (): BoardBlock | undefined => current().blocks.at(-1);

  for (const line of body.split('\n')) {
    const heading = SECTION.exec(line);
    if (heading) {
      flush();
      sections.push({ title: heading[1].trim(), blocks: [] });
      continue;
    }
    const targets = BULLET.test(line) ? [...line.matchAll(LINK)].map((found) => found[1]) : [];
    if (targets.length === 0) {
      prose.push(line);
      continue;
    }
    flush();
    const block = last();
    if (targets.length === 1) {
      const card = { target: targets[0], note: noteOf(line) };
      if (block?.kind === 'cards') block.cards.push(card);
      else current().blocks.push({ kind: 'cards', cards: [card] });
    } else {
      const tension = { targets, note: noteOf(line) };
      if (block?.kind === 'tensions') block.tensions.push(tension);
      else current().blocks.push({ kind: 'tensions', tensions: [tension] });
    }
  }
  flush();
  return sections.filter((section) => section.title !== null || section.blocks.length > 0);
}

/** Случаи принципа: сколько их и месяц последнего. Принцип без случаев — пока лозунг. */
export function cases(body: string): { count: number; last: string | null } {
  const months = body
    .split('\n')
    .map((line) => CASE.exec(line)?.[1])
    .filter((month): month is string => month !== undefined)
    .sort();
  return { count: months.length, last: months.at(-1) ?? null };
}

/** Все страницы, на которые ссылается доска, без повторов: их шапки нужны карточкам. */
export function targets(sections: BoardSection[]): string[] {
  const found = new Set<string>();
  for (const section of sections) {
    for (const block of section.blocks) {
      if (block.kind === 'cards') block.cards.forEach((card) => found.add(card.target));
      if (block.kind === 'tensions') block.tensions.forEach((tension) => tension.targets.forEach((t) => found.add(t)));
    }
  }
  return [...found];
}
