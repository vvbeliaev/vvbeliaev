<script lang="ts">
  import { file as fetchFile, type FileView } from './api';
  import Board from './Board.svelte';
  import { board, targets } from './board';
  import { fullDate, localDay, pageName } from './format';
  import Log from './Log.svelte';
  import { render } from './markdown';
  import { blocks, frontmatter } from './parse';

  let { path, tick }: { path: string; tick: number } = $props();

  type View = { status: 'loading' } | { status: 'ready'; file: FileView } | { status: 'failed'; message: string };
  let view = $state<View>({ status: 'loading' });

  $effect(() => {
    const wanted = path;
    void tick;
    let stale = false;
    fetchFile(wanted)
      .then((found) => {
        if (!stale) view = { status: 'ready', file: found };
      })
      .catch((error: unknown) => {
        if (!stale) view = { status: 'failed', message: error instanceof Error ? error.message : String(error) };
      });
    return () => {
      stale = true;
    };
  });

  const page = $derived(view.status === 'ready' && view.file.path.startsWith('pages/') ? frontmatter(view.file.text) : null);
  // Доска рисуется карточками принципов, а не сплошным текстом.
  const isBoard = $derived(view.status === 'ready' && view.file.path.startsWith('pages/boards/'));
  const held = $derived(
    isBoard && page ? targets(board(page.body)).filter((target) => target.startsWith('principles/')).length : 0,
  );
</script>

{#if view.status === 'failed'}
  <p class="failed">Не удалось прочитать <code>{path}</code>: {view.message}</p>
{:else if view.status === 'ready'}
  {#if page?.front}
    <article class:wide={isBoard}>
      <header>
        <p class="path">{view.file.path}</p>
        <h1>{page.front.title}</h1>
        {#if page.front.description}<p class="lede">{page.front.description}</p>{/if}
        <dl>
          {#if isBoard}<div><dt>принципов</dt><dd>{held}</dd></div>{/if}
          <div><dt>ревизия</dt><dd>{page.front.rev}</dd></div>
          <div><dt>обновлено</dt><dd>{fullDate(localDay(page.front.updated))}</dd></div>
          {#if page.front.aliases.length}
            <div><dt>также</dt><dd>{page.front.aliases.join(', ')}</dd></div>
          {/if}
        </dl>
      </header>
      {#if isBoard}
        <Board body={page.body} {tick} />
      {:else}
        <div class="prose">{@html render(page.body)}</div>
      {/if}
      {#if view.file.items?.length}
        <section>
          <h2>Дела</h2>
          <Log blocks={blocks(view.file.items.join('\n'))} />
        </section>
      {/if}
      {#if view.file.backlinks?.length}
        <footer>
          <h2>Сюда ссылаются</h2>
          <ul>
            {#each view.file.backlinks as target}
              <li><a href={`#/${target}`}>{pageName(target)}</a></li>
            {/each}
          </ul>
        </footer>
      {/if}
    </article>
  {:else if view.file.path === 'guide.md' || view.file.path.startsWith('pages/')}
    <div class="prose">{@html render(view.file.text)}</div>
  {:else}
    <Log blocks={blocks(view.file.text)} />
  {/if}
{/if}

<style>
  article {
    max-width: var(--measure);
  }

  article.wide {
    max-width: calc(var(--measure) + 22rem);
  }

  article.wide header,
  article.wide section,
  article.wide footer {
    max-width: var(--measure);
  }

  header {
    margin-bottom: 1.8rem;
    padding-bottom: 1.2rem;
    border-bottom: 1px solid var(--border);
  }

  .path {
    margin: 0 0 0.5rem;
    font: 400 0.76rem/1.6 var(--ff-mono);
    color: var(--muted-foreground);
  }

  h1 {
    font-size: 2rem;
  }

  .lede {
    margin: 0.5rem 0 0;
    font-size: 1.06rem;
    color: var(--muted-foreground);
  }

  dl {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem 1.6rem;
    margin: 1rem 0 0;
    font: 400 0.76rem/1.6 var(--ff-mono);
  }

  dl div {
    display: flex;
    gap: 0.5rem;
  }

  dt {
    color: var(--muted-foreground);
  }

  dd {
    margin: 0;
    color: var(--accent);
  }

  section,
  footer {
    margin-top: 2.4rem;
    padding-top: 1.1rem;
    border-top: 1px solid var(--border);
  }

  section h2,
  footer h2 {
    font-size: 0.95rem;
    margin-bottom: 0.5rem;
  }

  footer ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem 1.2rem;
    margin: 0;
    padding: 0;
    list-style: none;
    font: 400 0.82rem/1.8 var(--ff-mono);
  }

  .failed {
    max-width: var(--measure);
    color: var(--destructive);
  }
</style>
