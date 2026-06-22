<script lang="ts">
  let { start = 0 }: { start?: number } = $props();
  let count = $state(start);
</script>

<div class="my-6 flex items-center gap-3 rounded-lg border border-border p-4">
  <button
    type="button"
    onclick={() => (count -= 1)}
    class="size-8 rounded-md border border-border hover:bg-accent"
    aria-label="Decrease"
  >
    −
  </button>
  <span class="min-w-10 text-center font-mono text-lg tabular-nums">{count}</span>
  <button
    type="button"
    onclick={() => (count += 1)}
    class="size-8 rounded-md border border-border hover:bg-accent"
    aria-label="Increase"
  >
    +
  </button>
</div>
