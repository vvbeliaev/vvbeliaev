import { describe, expect, it } from 'vitest';

import { blocks, frontmatter, item } from './parse';

describe('item', () => {
  it('reads the fields that follow the title', () => {
    expect(
      item('- [ ] Позвонить в сервис  at:2026-10-12T14:00  every:FREQ=WEEKLY;BYDAY=MO  remind:-PT10M,-P1D  ^t_7k2m9xqa'),
    ).toEqual({
      status: 'open',
      title: 'Позвонить в сервис',
      id: 't_7k2m9xqa',
      at: '2026-10-12T14:00',
      every: 'FREQ=WEEKLY;BYDAY=MO',
      remind: '-PT10M,-P1D',
    });
  });

  it('keeps a double space and a colon inside the title', () => {
    expect(item('- [x] План:  черновик  due:2026-10-15  done:2026-10-14  ^t_abc')).toMatchObject({
      status: 'done',
      title: 'План:  черновик',
      due: '2026-10-15',
      done: '2026-10-14',
    });
  });

  it('reads a cancelled item with nothing but an id', () => {
    expect(item('- [-] Отменённое  ^t_abc')).toEqual({ status: 'cancelled', title: 'Отменённое', id: 't_abc' });
  });

  it('leaves an ordinary list line alone', () => {
    expect(item('- [ ] просто строка списка')).toBeNull();
    expect(item('- pages/people/anna.md')).toBeNull();
  });
});

describe('blocks', () => {
  it('splits an agenda into days and items', () => {
    const text = '# 2026-10-12 — 2026-10-18\n\n## overdue\n- [ ] Старое  due:2026-10-01  ^t_old\n\n## 2026-10-12 Mon\n- [ ] Встреча  at:2026-10-12T14:00  ^e_meet\n\n## 2026-10-13 Tue\n';
    expect(blocks(text).map((block) => block.kind)).toEqual(['heading', 'heading', 'item', 'day', 'item', 'day']);
    expect(blocks(text)[3]).toEqual({ kind: 'day', date: '2026-10-12' });
  });

  it('reads a fact heading and keeps its text together', () => {
    const text = '## 09:41 · f_abc · mcp:Claude Code · said\n\nКупить фильтр\nдо пятницы\n';
    expect(blocks(text)).toEqual([
      { kind: 'fact', time: '09:41', id: 'f_abc', client: 'mcp:Claude Code', origin: 'said' },
      { kind: 'text', text: '\nКупить фильтр\nдо пятницы\n' },
    ]);
  });

  it('drops text that is only blank lines', () => {
    expect(blocks('# inbox\n\n\n')).toEqual([{ kind: 'heading', level: 1, text: 'inbox' }]);
  });
});

describe('frontmatter', () => {
  it('reads the header the server writes', () => {
    const text = '---\ntitle: "Аня: \\"заметки\\""\ndescription: "Коллега"\naliases: ["Анна", "anya"]\nrev: 3\nupdated: 2026-10-12T10:00Z\n---\n\nТело страницы\n';
    expect(frontmatter(text)).toEqual({
      front: { title: 'Аня: "заметки"', description: 'Коллега', aliases: ['Анна', 'anya'], rev: 3, updated: '2026-10-12T10:00Z' },
      body: 'Тело страницы\n',
    });
  });

  it('returns the text as is when there is no header', () => {
    expect(frontmatter('# guide\n')).toEqual({ front: null, body: '# guide\n' });
  });
});
