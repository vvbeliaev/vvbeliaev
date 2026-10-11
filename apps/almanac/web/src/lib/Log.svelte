<script lang="ts">
  // Журнал: слева колонка времени, справа записи. Так показаны и повестка, и дела, и факты.
  import { dayOfMonth, heading, origin, pageName, remind, repeat, shortDate, today, weekday } from './format';
  import { render } from './markdown';
  import type { Block, Item } from './parse';

  let { blocks }: { blocks: Block[] } = $props();

  const now = today();
  // В повестке день уже стоит в колонке времени; в остальных файлах дату показывает сама строка.
  const dated = $derived(blocks.some((block) => block.kind === 'day'));

  const STATUS: Record<Item['status'], string> = { open: 'открыто', done: 'сделано', cancelled: 'отменено' };
  const late = (item: Item): boolean => item.status === 'open' && item.due !== undefined && item.due < now;
</script>

<div class="log">
  {#each blocks as block}
    {#if block.kind === 'heading'}
      <svelte:element this={`h${Math.min(block.level, 3)}`} class="cell" class:alarm={block.text === 'overdue'}>
        {heading(block.text)}
      </svelte:element>
    {:else if block.kind === 'day'}
      <div class="gutter day" class:today={block.date === now}>
        {weekday(block.date)} <b>{dayOfMonth(block.date)}</b>
      </div>
      <div class="cell day">{block.date === now ? 'сегодня' : ''}</div>
    {:else if block.kind === 'fact'}
      <div class="gutter">{block.time}</div>
      <div class="cell fact">
        <span>{block.id}</span>
        <span>{block.client}</span>
        <span class:foreign={block.origin !== 'said'}>{origin(block.origin)}</span>
      </div>
    {:else if block.kind === 'item'}
      {@const item = block.item}
      <div class="gutter">{item.at ? item.at.slice(11, 16) : ''}</div>
      <div class="cell item" class:closed={item.status !== 'open'}>
        <span class="box" data-status={item.status} role="img" aria-label={STATUS[item.status]}></span>
        <div>
          <span class="title">{item.title}</span>
          <span class="meta">
            {#if item.at && !dated}<span>{shortDate(item.at.slice(0, 10))}</span>{/if}
            {#if item.due}<span class:late={late(item)}>срок {shortDate(item.due)}</span>{/if}
            {#if item.every}<span>{repeat(item.every)}</span>{/if}
            {#if item.remind}<span>напомнить {item.remind.split(',').map(remind).join(', ')}</span>{/if}
            {#if item.list}<a href={`#/items/lists/${item.list}.md`}>{item.list}</a>{/if}
            {#if item.page}<a href={`#/pages/${pageName(item.page)}.md`}>{pageName(item.page)}</a>{/if}
            {#if item.done}<span>закрыто {shortDate(item.done)}</span>{/if}
            <span class="id">{item.id}</span>
          </span>
        </div>
      </div>
    {:else}
      <div class="cell prose">{@html render(block.text, true)}</div>
    {/if}
  {/each}
</div>

<style>
  .log {
    position: relative;
    display: grid;
    grid-template-columns: var(--gutter) minmax(0, 1fr);
    column-gap: 1.75rem;
    row-gap: 0.45rem;
    max-width: calc(var(--gutter) + 1.75rem + var(--measure));
  }

  /* Ось времени между колонками. */
  .log::before {
    content: "";
    position: absolute;
    top: 0.4rem;
    bottom: 0;
    left: calc(var(--gutter) + 0.875rem);
    width: 1px;
    background: linear-gradient(var(--border) 70%, transparent);
  }

  .gutter {
    grid-column: 1;
    text-align: right;
    font: 500 0.78rem/2.05 var(--ff-mono);
    color: var(--accent);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .cell {
    grid-column: 2;
    min-width: 0;
  }

  h1.cell {
    font-size: 1.7rem;
    margin-bottom: 0.9rem;
  }

  h2.cell,
  h3.cell {
    font-size: 1.05rem;
    margin-top: 1.3rem;
  }

  .alarm {
    color: var(--destructive);
  }

  .day {
    margin-top: 1.25rem;
  }

  .gutter.day {
    position: relative;
    color: var(--muted-foreground);
    font-size: 0.8rem;
  }

  .gutter.day b {
    color: var(--foreground);
    font-weight: 600;
    margin-left: 0.15em;
  }

  /* Отметка дня на оси. Сегодняшняя — единственное, что на странице светится. */
  .gutter.day::after {
    content: "";
    position: absolute;
    top: 50%;
    right: -0.875rem;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    translate: 50% -50%;
    background: var(--background);
    border: 1px solid var(--muted-foreground);
  }

  .gutter.day.today::after {
    border-color: var(--primary);
    background: var(--primary);
    box-shadow: 0 0 var(--glow-blur) calc(var(--glow-spread) * -0.5) color-mix(in oklch, var(--primary) 65%, transparent);
  }

  .cell.day {
    font: 500 0.78rem/2.05 var(--ff-mono);
    color: var(--primary);
  }

  .item {
    display: flex;
    gap: 0.65rem;
    align-items: baseline;
  }

  .box {
    flex: none;
    width: 0.8rem;
    height: 0.8rem;
    translate: 0 0.08rem;
    border: 1px solid var(--muted-foreground);
    border-radius: 0.2rem;
  }

  .box[data-status="done"] {
    background: var(--muted-foreground);
    border-color: var(--muted-foreground);
  }

  .box[data-status="cancelled"] {
    background: linear-gradient(var(--muted-foreground), var(--muted-foreground)) center / 60% 1px no-repeat;
  }

  .closed .title {
    color: var(--muted-foreground);
    text-decoration: line-through;
    text-decoration-color: var(--border);
  }

  .meta {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 0 0.9rem;
    margin-left: 0.5rem;
    font: 400 0.74rem/1.6 var(--ff-mono);
    color: var(--muted-foreground);
  }

  .meta a {
    color: var(--accent);
  }

  .meta .late {
    color: var(--destructive);
  }

  .meta .id {
    opacity: 0.55;
  }

  .fact {
    display: flex;
    flex-wrap: wrap;
    gap: 0 0.9rem;
    margin-top: 0.9rem;
    font: 400 0.74rem/2.2 var(--ff-mono);
    color: var(--muted-foreground);
  }

  .fact .foreign {
    color: var(--accent);
  }

  @media (max-width: 40rem) {
    .log {
      --gutter: 3.1rem;
      column-gap: 1.25rem;
    }

    .log::before {
      left: calc(var(--gutter) + 0.625rem);
    }

    .gutter.day::after {
      right: -0.625rem;
    }

    .meta {
      display: flex;
      margin-left: 0;
    }
  }
</style>
