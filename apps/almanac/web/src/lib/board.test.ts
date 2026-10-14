import { describe, expect, it } from 'vitest';

import { board, cases, targets } from './board';

const BODY = `Как я выбираю, что строить.

## Шаг
- [[principles/by-hand-first]] — главный фильтр
- [[principles/contact-not-code]]

Под вопросом:
- просто строка без ссылки

## Напряжения
- [[principles/interest-required]] ⟷ [[principles/bottleneck|узкое место]] — интерес против рычага
- [[principles/a]] / [[principles/b]]
`;

describe('board', () => {
  it('splits a board into sections of prose, cards and tensions', () => {
    expect(board(BODY)).toEqual([
      { title: null, blocks: [{ kind: 'prose', text: 'Как я выбираю, что строить.\n' }] },
      {
        title: 'Шаг',
        blocks: [
          {
            kind: 'cards',
            cards: [
              { target: 'principles/by-hand-first', note: 'главный фильтр' },
              { target: 'principles/contact-not-code', note: '' },
            ],
          },
          { kind: 'prose', text: '\nПод вопросом:\n- просто строка без ссылки\n' },
        ],
      },
      {
        title: 'Напряжения',
        blocks: [
          {
            kind: 'tensions',
            tensions: [
              { targets: ['principles/interest-required', 'principles/bottleneck'], note: 'интерес против рычага' },
              { targets: ['principles/a', 'principles/b'], note: '' },
            ],
          },
        ],
      },
    ]);
  });

  it('keeps a link inside running text as prose', () => {
    expect(board('Смотри [[principles/a]] и дальше.')).toEqual([
      { title: null, blocks: [{ kind: 'prose', text: 'Смотри [[principles/a]] и дальше.' }] },
    ]);
  });

  it('lists every page a board links once', () => {
    expect(targets(board(BODY))).toEqual([
      'principles/by-hand-first',
      'principles/contact-not-code',
      'principles/interest-required',
      'principles/bottleneck',
      'principles/a',
      'principles/b',
    ]);
  });
});

describe('cases', () => {
  it('counts the list items that start with a month and finds the latest', () => {
    const body = '## Случаи\n- 2026-10 — overture\n- 2025-03 — раньше\n* 2026-11: ещё\n- без даты\nтекст 2026-12';
    expect(cases(body)).toEqual({ count: 3, last: '2026-11' });
  });

  it('says there are none when nothing is dated', () => {
    expect(cases('Принцип без истории.')).toEqual({ count: 0, last: null });
  });
});
