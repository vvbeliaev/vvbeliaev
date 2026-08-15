// @ts-check
import { defineConfig } from "astro/config";
import svelte from "@astrojs/svelte";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";

// https://astro.build/config
export default defineConfig({
  // Боевой домен: sitemap и canonical-ссылки строятся от него.
  site: "https://vvbeliaev.dev",
  output: "static",
  // Bilingual: English at the root, Russian under /ru.
  i18n: {
    locales: ["en", "ru"],
    defaultLocale: "en",
    routing: { prefixDefaultLocale: false },
  },
  integrations: [svelte(), mdx(), sitemap()],
  vite: {
    plugins: [tailwindcss()],
  },
});
