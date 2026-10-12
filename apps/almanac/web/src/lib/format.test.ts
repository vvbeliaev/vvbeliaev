import { describe, expect, it } from 'vitest';

import { closedMonth, factDay, heading, pageName, remind, repeat, span } from './format';

describe('format', () => {
  it('names the headings the server writes', () => {
    expect(heading('overdue')).toBe('Просрочено');
    expect(heading('2026-10-12')).toBe('12 октября 2026');
    expect(heading('2026-10-12 — 2026-10-18')).toBe('12 окт — 18 октября 2026');
    expect(heading('Свой заголовок')).toBe('Свой заголовок');
  });

  it('reads reminder offsets', () => {
    expect(remind('PT10M')).toBe('за 10 мин');
    expect(remind('P1D')).toBe('за 1 д');
    expect(remind('P1DT2H')).toBe('за 1 д 2 ч');
    expect(remind('PT0M')).toBe('в срок');
    expect(remind('странное')).toBe('странное');
  });

  it('says simple repeats in words and keeps the rest', () => {
    expect(repeat('FREQ=WEEKLY')).toBe('каждую неделю');
    expect(repeat('FREQ=WEEKLY;BYDAY=MO,TH')).toBe('weekly;byday=mo,th');
  });

  it('says a whole day without a time and a range with both ends', () => {
    expect(span('2026-10-20', undefined, true)).toBe('20 окт');
    expect(span('2026-10-20', undefined, false)).toBe('весь день');
    expect(span('2026-10-20', '2026-10-20', false)).toBe('весь день');
    expect(span('2026-10-20', '2026-10-25', true)).toBe('20 окт — 25 окт');
    expect(span('2026-10-20', '2026-10-25', false)).toBe('20 окт — 25 окт');
  });

  it('keeps the time of a moment in the gutter and names only the end', () => {
    expect(span('2026-10-14T18:00', undefined, false)).toBe('');
    expect(span('2026-10-14T18:00', undefined, true)).toBe('14 окт');
    expect(span('2026-10-14T18:00', '2026-10-14T19:30', false)).toBe('до 19:30');
    expect(span('2026-10-14T18:00', '2026-10-14T19:30', true)).toBe('14 окт, до 19:30');
    expect(span('2026-10-14T22:00', '2026-10-15T06:00', false)).toBe('14 окт, 22:00 — 15 окт, 06:00');
  });

  it('treats midnight with a time as a moment, not a whole day', () => {
    expect(span('2026-10-14T00:00', undefined, false)).toBe('');
    expect(span('2026-10-14T00:00', '2026-10-14T01:00', false)).toBe('до 01:00');
  });

  it('reads dates out of tree paths', () => {
    expect(factDay('facts/2026/10-12.md')).toBe('2026-10-12');
    expect(factDay('pages/people/anna.md')).toBeNull();
    expect(closedMonth('items/done/2026-10.md')).toBe('окт 2026');
    expect(pageName('pages/people/anna.md')).toBe('people/anna');
    expect(pageName('people/anna')).toBe('people/anna');
  });
});
