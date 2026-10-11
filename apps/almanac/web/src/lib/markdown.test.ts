// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { render } from './markdown';

function dom(markdown: string): HTMLElement {
  const holder = document.createElement('div');
  holder.innerHTML = render(markdown);
  return holder;
}

describe('render', () => {
  it('turns wiki links into links to pages', () => {
    const links = dom('См. [[people/anna]] и [[topics/postgres|про базу]].').querySelectorAll('a');
    expect([...links].map((link) => [link.getAttribute('href'), link.textContent])).toEqual([
      ['#/pages/people/anna.md', 'people/anna'],
      ['#/pages/topics/postgres.md', 'про базу'],
    ]);
    expect(links[0].getAttribute('target')).toBeNull();
  });

  it('opens outside links in a new tab without passing anything along', () => {
    const link = dom('[источник](https://example.com/a)').querySelector('a');
    expect(link?.getAttribute('target')).toBe('_blank');
    expect(link?.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('drops scripts and script links', () => {
    const html = render('[x](javascript:alert(1)) <a href="JaVaScRiPt:alert(1)">y</a> <script>alert(1)</script> <b onclick="alert(1)">z</b>');
    expect(html.toLowerCase()).not.toContain('javascript:');
    expect(html).not.toContain('<script');
    expect(html).not.toContain('onclick');
  });

  // Чтение записи не должно ходить на чужой сервер — и там, где сайт отдан без политики содержимого.
  it('leaves nothing that would load a resource', () => {
    const foreign = [
      '![pixel](https://example.com/1.png)',
      '<img src="https://example.com/2.png">',
      '<svg><image href="https://example.com/3.png"/></svg>',
      '<svg><filter><feImage href="https://example.com/4.png"/></filter></svg>',
      '<table background="https://example.com/5.png"><tr><td background="https://example.com/6.png">x</td></tr></table>',
      '<p style="background:url(https://example.com/7.png)">y</p>',
      '<video poster="https://example.com/8.png"></video>',
      '<link rel="stylesheet" href="https://example.com/9.css">',
      '<a href="https://example.com/ok" ping="https://example.com/10">z</a>',
    ].join('\n\n');
    const holder = dom(foreign);
    const html = holder.innerHTML;
    for (let index = 1; index <= 10; index += 1) expect(html).not.toContain(`example.com/${index}`);
    expect(holder.querySelector('img, svg, image, video, link, [style], [background], [ping]')).toBeNull();
    expect(holder.querySelector('a')?.getAttribute('href')).toBe('https://example.com/ok');
  });
});
