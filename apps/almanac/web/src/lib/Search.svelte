<script lang="ts">
  import { grep, type Match } from './api';

  let { pattern }: { pattern: string } = $props();

  type View = { status: 'loading' } | { status: 'ready'; found: Match[] } | { status: 'failed'; message: string };
  let view = $state<View>({ status: 'loading' });

  $effect(() => {
    const wanted = pattern;
    let stale = false;
    view = { status: 'loading' };
    grep(wanted)
      .then((found) => {
        if (!stale) view = { status: 'ready', found };
      })
      .catch((error: unknown) => {
        if (!stale) view = { status: 'failed', message: error instanceof Error ? error.message : String(error) };
      });
    return () => {
      stale = true;
    };
  });

  const groups = $derived.by(() => {
    const byPath = new Map<string, Match[]>();
    if (view.status === 'ready') {
      for (const match of view.found) byPath.set(match.path, [...(byPath.get(match.path) ?? []), match]);
    }
    return [...byPath];
  });
</script>

<section>
  <h1>Найдено по <code>{pattern}</code></h1>
  {#if view.status === 'failed'}
    <p class="failed">Поиск не выполнен: {view.message}</p>
  {:else if view.status === 'ready' && groups.length === 0}
    <p>Ничего. Поиск — регулярное выражение без учёта регистра по страницам, фактам и делам: попробуй слово короче.</p>
  {:else}
    {#each groups as [path, matches]}
      <div class="hit">
        <a href={`#/${path}`}>{path}</a>
        <ol>
          {#each matches as match}
            <li><span>{match.line}</span>{match.text}</li>
          {/each}
        </ol>
      </div>
    {/each}
  {/if}
</section>

<style>
  section {
    max-width: calc(var(--measure) + 6rem);
  }

  h1 {
    font-size: 1.5rem;
    margin-bottom: 1.4rem;
  }

  h1 code {
    font: 500 0.85em var(--ff-mono);
    color: var(--primary);
  }

  p {
    max-width: var(--measure);
    color: var(--muted-foreground);
  }

  .failed {
    color: var(--destructive);
  }

  .hit {
    margin-bottom: 1.3rem;
  }

  .hit a {
    font: 500 0.82rem/1.8 var(--ff-mono);
  }

  ol {
    margin: 0.2rem 0 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: grid;
    grid-template-columns: 2.6rem minmax(0, 1fr);
    gap: 0.9rem;
    overflow-wrap: anywhere;
  }

  li span {
    text-align: right;
    font: 400 0.76rem/2.1 var(--ff-mono);
    color: var(--muted-foreground);
    font-variant-numeric: tabular-nums;
  }
</style>
