<script lang="ts">
  // Доска принципов: карточки по разделам и напряжения между принципами. Шапки карточек —
  // из самих страниц: заголовок-утверждение, пояснение и случаи, по которым видно, жив ли принцип.
  import { file as fetchFile } from './api';
  import { board, cases, targets } from './board';
  import { closedMonth, pageName } from './format';
  import { render } from './markdown';
  import { frontmatter } from './parse';

  let { body, tick }: { body: string; tick: number } = $props();

  type Head = { title: string; description: string; count: number; last: string | null } | 'missing';

  const sections = $derived(board(body));
  let heads = $state<Record<string, Head>>({});

  $effect(() => {
    const wanted = targets(sections);
    void tick;
    let stale = false;
    Promise.allSettled(wanted.map((target) => fetchFile(`pages/${target}.md`))).then((results) => {
      if (stale) return;
      const found: Record<string, Head> = {};
      results.forEach((result, index) => {
        if (result.status === 'rejected') {
          found[wanted[index]] = 'missing';
          return;
        }
        const page = frontmatter(result.value.text);
        found[wanted[index]] = {
          title: page.front?.title || pageName(`pages/${wanted[index]}.md`),
          description: page.front?.description ?? '',
          ...cases(page.body),
        };
      });
      heads = found;
    });
    return () => {
      stale = true;
    };
  });

  const href = (target: string): string => `#/pages/${target}.md`;
  const titleOf = (target: string): string => {
    const head = heads[target];
    return head && head !== 'missing' ? head.title : pageName(`pages/${target}.md`);
  };
</script>

<div class="board">
  {#each sections as section}
    <section>
      {#if section.title}<h2>{section.title}</h2>{/if}
      {#each section.blocks as block}
        {#if block.kind === 'prose'}
          <div class="prose">{@html render(block.text)}</div>
        {:else if block.kind === 'cards'}
          <ul class="cards">
            {#each block.cards as card}
              {@const head = heads[card.target]}
              <li>
                <a class="card" class:pending={!head} class:missing={head === 'missing'} href={href(card.target)}>
                  <h3>{titleOf(card.target)}</h3>
                  {#if head && head !== 'missing' && head.description}<p class="why">{head.description}</p>{/if}
                  {#if card.note}<p class="note">{card.note}</p>{/if}
                  <p class="meta">
                    {#if head === 'missing'}
                      страницы нет
                    {:else if head && head.count > 0}
                      случаев <b>{head.count}</b> · последний {closedMonth(`${head.last}.md`)}
                    {:else if head}
                      случаев пока нет
                    {/if}
                  </p>
                </a>
              </li>
            {/each}
          </ul>
        {:else}
          <ul class="tensions">
            {#each block.tensions as tension}
              <li>
                <div class="poles" class:pair={tension.targets.length === 2}>
                  {#each tension.targets as target, index}
                    {#if index > 0}<span class="rule" role="img" aria-label="против"></span>{/if}
                    <a href={href(target)} class:missing={heads[target] === 'missing'}>{titleOf(target)}</a>
                  {/each}
                </div>
                {#if tension.note}<p class="note">{tension.note}</p>{/if}
              </li>
            {/each}
          </ul>
        {/if}
      {/each}
    </section>
  {/each}
</div>

<style>
  .board {
    display: grid;
    gap: 2.2rem;
  }

  section {
    display: grid;
    gap: 1rem;
  }

  section > h2 {
    font-size: 1.15rem;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(15.5rem, 1fr));
    gap: 0.8rem;
  }

  .cards li {
    display: flex;
  }

  /* Карточка — панель HUD: поднятый фон, тонкая рамка; угольком светится только под указателем. */
  .card {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    width: 100%;
    padding: 0.95rem 1.05rem 0.85rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: color-mix(in oklch, var(--card) 82%, transparent);
    color: var(--foreground);
    text-decoration: none;
    transition:
      border-color 0.2s,
      box-shadow 0.2s;
  }

  .card:hover {
    border-color: color-mix(in oklch, var(--primary) 30%, var(--border));
    box-shadow: 0 0 var(--glow-blur) var(--glow-spread) color-mix(in oklch, var(--primary) 45%, transparent);
  }

  .card h3 {
    font-size: 1.04rem;
    line-height: 1.3;
  }

  .card.pending h3 {
    color: var(--muted-foreground);
  }

  .why {
    margin: 0;
    font-size: 0.92rem;
    line-height: 1.5;
    color: var(--muted-foreground);
  }

  .note {
    margin: 0;
    padding-left: 0.6rem;
    border-left: 2px solid color-mix(in oklch, var(--accent) 45%, transparent);
    font-size: 0.88rem;
    line-height: 1.45;
    color: var(--foreground);
  }

  .meta {
    margin: auto 0 0;
    padding-top: 0.3rem;
    font: 400 0.72rem/1.6 var(--ff-mono);
    color: var(--muted-foreground);
  }

  .meta b {
    font-weight: 500;
    color: var(--accent);
  }

  .card.missing .meta {
    color: var(--destructive);
  }

  .tensions {
    display: grid;
    gap: 0.9rem;
    max-width: calc(var(--measure) + 10rem);
  }

  .poles {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem 0.75rem;
    font: 600 0.98rem/1.35 var(--ff-display);
  }

  /* Пара — перетягивание: полюса по обе стороны линии, каждый прижат к ней. */
  .poles.pair {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 3rem minmax(0, 1fr);
  }

  .poles.pair a:first-child {
    text-align: right;
  }

  .poles.pair .rule {
    min-width: 0;
  }

  .poles a.missing {
    color: var(--muted-foreground);
  }

  .poles a {
    color: var(--foreground);
    text-decoration: none;
  }

  .poles a:hover {
    color: var(--primary);
  }

  /* Линия созвездия между полюсами: холодная, пунктиром — связь, а не стрелка. */
  .rule {
    flex: 0 1 3.5rem;
    min-width: 1.5rem;
    border-top: 1px dashed color-mix(in oklch, var(--accent) 60%, transparent);
  }

  .tensions li {
    padding: 0.8rem 1rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: color-mix(in oklch, var(--card) 60%, transparent);
  }

  .tensions .note {
    margin-top: 0.55rem;
    border-left: 0;
    padding-left: 0;
    text-align: center;
    color: var(--muted-foreground);
  }

  @media (max-width: 40rem) {
    .poles.pair {
      grid-template-columns: minmax(0, 1fr);
      justify-items: start;
    }

    .poles.pair a:first-child {
      text-align: left;
    }

    .poles.pair .rule {
      width: 3rem;
    }

    .tensions .note {
      text-align: left;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .card {
      transition: none;
    }
  }
</style>
