import { describe, expect, it } from 'vitest';

import { closedMonth, factDay, heading, pageName, remind, repeat } from './format';

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

  it('reads dates out of tree paths', () => {
    expect(factDay('facts/2026/10-12.md')).toBe('2026-10-12');
    expect(factDay('pages/people/anna.md')).toBeNull();
    expect(closedMonth('items/done/2026-10.md')).toBe('окт 2026');
    expect(pageName('pages/people/anna.md')).toBe('people/anna');
    expect(pageName('people/anna')).toBe('people/anna');
  });
});
