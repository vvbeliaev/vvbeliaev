<script lang="ts">
  import { onMount } from 'svelte';

  import { tree, type Entry } from './lib/api';
  import Rail from './lib/Rail.svelte';
  import Reader from './lib/Reader.svelte';
  import Search from './lib/Search.svelte';

  const HOME = 'views/week.md';

  type Route = { kind: 'file'; path: string } | { kind: 'grep'; pattern: string };

  function decoded(raw: string): string {
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }

  // Адрес — путь файла дерева после решётки: `#/pages/people/anna.md`, поиск — `#/grep/<выражение>`.
  function routeOf(hash: string): Route {
    const raw = hash.replace(/^#\/?/, '');
    if (raw.startsWith('grep/')) return { kind: 'grep', pattern: decoded(raw.slice(5)) };
    return { kind: 'file', path: raw ? decoded(raw) : HOME };
  }

  let route = $state<Route>(routeOf(location.hash));
  let entries = $state<Entry[]>([]);
  let failure = $state('');
  let query = $state('');
  let menu = $state(false);
  // Записи меняются снаружи, через MCP: вернулся на вкладку — перечитали.
  let tick = $state(0);

  function load(): void {
    tree()
      .then((found) => {
        entries = found;
        failure = '';
      })
      .catch((error: unknown) => {
        failure = error instanceof Error ? error.message : String(error);
      });
  }

  onMount(() => {
    const onHash = (): void => {
      route = routeOf(location.hash);
      window.scrollTo(0, 0);
    };
    const onFocus = (): void => {
      tick += 1;
      load();
    };
    window.addEventListener('hashchange', onHash);
    window.addEventListener('focus', onFocus);
    load();
    return () => {
      window.removeEventListener('hashchange', onHash);
      window.removeEventListener('focus', onFocus);
    };
  });

  function search(event: SubmitEvent): void {
    event.preventDefault();
    const pattern = query.trim();
    if (pattern) location.hash = `#/grep/${encodeURIComponent(pattern)}`;
  }
</script>

<div class="shell">
  <aside>
    <div class="brand">
      <a href="#/">almanac<span aria-hidden="true">_</span></a>
      <button type="button" aria-expanded={menu} aria-controls="rail" onclick={() => (menu = !menu)}>
        {menu ? 'Скрыть разделы' : 'Разделы'}
      </button>
    </div>
    <div id="rail" class:open={menu}>
      <Rail {entries} current={route.kind === 'file' ? route.path : ''} onnavigate={() => (menu = false)} />
    </div>
  </aside>

  <main>
    <form role="search" onsubmit={search}>
      <label class="sr-only" for="query">Поиск по записям</label>
      <input id="query" type="search" bind:value={query} placeholder="Найти в записях: слово или регулярное выражение" autocomplete="off" spellcheck="false" />
    </form>
    {#if failure}
      <p class="failed">Не удалось прочитать дерево: {failure}. Сервер поднят? <code>make status</code></p>
    {/if}
    {#if route.kind === 'grep'}
      <Search pattern={route.pattern} />
    {:else}
      <Reader path={route.path} {tick} />
    {/if}
  </main>
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns: 16.5rem minmax(0, 1fr);
    min-height: 100dvh;
  }

  aside {
    position: sticky;
    top: 0;
    align-self: start;
    height: 100dvh;
    overflow-y: auto;
    padding: 1.6rem 1.25rem 2.5rem 2.1rem;
    border-right: 1px solid var(--border);
    background: color-mix(in oklch, var(--card) 70%, transparent);
  }

  .brand {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 1.9rem;
  }

  .brand a {
    font: 700 1.2rem/1 var(--ff-display);
    letter-spacing: -0.02em;
    color: var(--foreground);
    text-decoration: none;
  }

  /* Курсор полевого журнала — ритуал из DESIGN.md. */
  .brand a span {
    color: var(--primary);
    animation: blink 1.1s step-end infinite;
  }

  .brand button {
    display: none;
    padding: 0.2rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: none;
    font: 400 0.8rem/1.6 var(--ff-mono);
    color: var(--muted-foreground);
    cursor: pointer;
  }

  main {
    min-width: 0;
    padding: 1.4rem 2rem 5rem 2.5rem;
  }

  form {
    max-width: calc(var(--measure) + 6rem);
    margin-bottom: 2.4rem;
  }

  input {
    width: 100%;
    padding: 0.55rem 0.85rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: color-mix(in oklch, var(--card) 80%, transparent);
    font: 400 0.9rem/1.5 var(--ff-body);
    color: var(--foreground);
  }

  input::placeholder {
    color: var(--muted-foreground);
  }

  input:focus-visible {
    outline: none;
    border-color: var(--primary);
  }

  .failed {
    max-width: var(--measure);
    color: var(--destructive);
  }

  .failed code {
    font: 0.86em var(--ff-mono);
  }

  @media (max-width: 52rem) {
    .shell {
      grid-template-columns: minmax(0, 1fr);
    }

    aside {
      position: static;
      height: auto;
      padding: 1rem 1rem 1rem 1.85rem;
      border-right: 0;
      border-bottom: 1px solid var(--border);
    }

    .brand {
      margin-bottom: 0;
    }

    .brand button {
      display: block;
    }

    #rail {
      display: none;
      margin-top: 1.4rem;
    }

    #rail.open {
      display: block;
    }

    main {
      padding: 1.1rem 1rem 4rem;
    }
  }
</style>
