import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  // Сервер almanac, поднятый `make up`; другой адрес — ALMANAC_URL=… pnpm dev.
  const target = loadEnv(mode, '.', 'ALMANAC_').ALMANAC_URL ?? 'http://127.0.0.1:8910';
  // `changeOrigin`: сервер сверяет Host запроса со своим адресом.
  const proxied = { target, changeOrigin: true };
  return {
    plugins: [svelte()],
    // Ничего не встраивать как data:-адреса: сервер отдаёт сайт с `font-src 'self'`.
    build: { assetsInlineLimit: 0 },
    server: { host: '127.0.0.1', proxy: { '/api': proxied, '/login': proxied, '/logout': proxied } },
  };
});
