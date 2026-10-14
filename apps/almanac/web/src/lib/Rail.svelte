<script lang="ts">
  import type { Entry } from './api';
  import { closedMonth, factDay, shortDate, stem } from './format';

  let { entries, current, onnavigate }: { entries: Entry[]; current: string; onnavigate: () => void } = $props();

  const NOW = [
    { path: 'views/today.md', label: 'Сегодня' },
    { path: 'views/week.md', label: 'Неделя' },
    { path: 'views/inbox.md', label: 'Входящие' },
  ];
  const DAYS_SHOWN = 10;

  const files = $derived(entries.filter((entry) => entry.kind === 'file'));
  const types = $derived(
    entries
      .filter((entry) => entry.kind === 'dir' && /^pages\/[^/]+$/.test(entry.path))
      .map((dir) => ({ ...dir, pages: files.filter((entry) => entry.path.startsWith(`${dir.path}/`)) })),
  );
  const lists = $derived(files.filter((entry) => entry.path.startsWith('items/lists/')));
  const closed = $derived(files.filter((entry) => entry.path.startsWith('items/done/')).reverse());
  const past = $derived(files.filter((entry) => entry.path.startsWith('items/past/')).reverse());
  const days = $derived(files.filter((entry) => entry.path.startsWith('facts/')).reverse());

  let everyDay = $state(false);
  const shownDays = $derived(everyDay ? days : days.slice(0, DAYS_SHOWN));

  function dayLabel(path: string): string {
    const date = factDay(path);
    if (!date) return stem(path);
    const year = date.slice(0, 4);
    return year === String(new Date().getFullYear()) ? shortDate(date) : `${shortDate(date)} ${year}`;
  }
</script>

{#snippet link(path: string, label: string, hint: string | null = null)}
  <li>
    <a href={`#/${path}`} aria-current={current === path ? 'page' : undefined} title={hint} onclick={onnavigate}>
      {label}
    </a>
  </li>
{/snippet}

<nav aria-label="Разделы">
  <section>
    <h2>Сейчас</h2>
    <ul>
      {#each NOW as now}{@render link(now.path, now.label)}{/each}
    </ul>
  </section>

  <section>
    <h2>Страницы</h2>
    {#each types as type}
      <h3 class:empty={type.pages.length === 0} title={type.description}>{stem(type.path)}</h3>
      {#if type.pages.length}
        <ul>
          {#each type.pages as page}{@render link(page.path, stem(page.path), page.description)}{/each}
        </ul>
      {/if}
    {/each}
  </section>

  <section>
    <h2>Дела</h2>
    <ul>
      {@render link('items/tasks.md', 'Задачи')}
      {@render link('items/events.md', 'События')}
      {#each lists as list}{@render link(list.path, stem(list.path))}{/each}
    </ul>
    {#if closed.length}
      <h3>закрытые</h3>
      <ul>
        {#each closed as month}{@render link(month.path, closedMonth(month.path))}{/each}
      </ul>
    {/if}
    {#if past.length}
      <h3>прошедшие события</h3>
      <ul>
        {#each past as month}{@render link(month.path, closedMonth(month.path))}{/each}
      </ul>
    {/if}
  </section>

  <section>
    <h2>Факты</h2>
    {#if days.length}
      <ul>
        {#each shownDays as day}{@render link(day.path, dayLabel(day.path))}{/each}
      </ul>
      {#if days.length > DAYS_SHOWN && !everyDay}
        <button type="button" onclick={() => (everyDay = true)}>Все дни: {days.length}</button>
      {/if}
    {:else}
      <p>Пока ни одного.</p>
    {/if}
  </section>

  <section>
    <h2>Устройство</h2>
    <ul>
      {@render link('guide.md', 'Правила')}
      {@render link('views/lint.md', 'Проверка ссылок')}
    </ul>
  </section>
</nav>

<style>
  nav {
    display: grid;
    gap: 1.6rem;
    font-size: 0.94rem;
  }

  /* Подписи разделов — приборные: моно, прописные, разрядка (DESIGN.md, типографика). */
  h2 {
    margin-bottom: 0.45rem;
    font: 500 0.66rem/1.6 var(--ff-mono);
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: var(--muted-foreground);
  }

  h3 {
    margin: 0.55rem 0 0.1rem;
    font: 400 0.78rem/1.6 var(--ff-mono);
    letter-spacing: 0;
    color: var(--accent);
  }

  h3.empty {
    color: var(--muted-foreground);
    opacity: 0.6;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  a {
    display: block;
    margin-left: -0.85rem;
    padding: 0.12rem 0 0.12rem 0.85rem;
    border-left: 2px solid transparent;
    color: var(--muted-foreground);
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  a:hover {
    color: var(--foreground);
  }

  a[aria-current="page"] {
    color: var(--foreground);
    border-left-color: var(--primary);
  }

  p {
    margin: 0;
    color: var(--muted-foreground);
  }

  button {
    margin-top: 0.3rem;
    padding: 0;
    border: 0;
    background: none;
    font: 400 0.78rem/1.6 var(--ff-mono);
    color: var(--accent);
    cursor: pointer;
  }

  button:hover {
    color: var(--foreground);
  }
</style>
