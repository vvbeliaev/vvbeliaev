// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import icon from "astro-icon";
import tailwindcss from "@tailwindcss/vite";

// https://astro.build/config
export default defineConfig({
  site: "https://cogisoft.dev",
  output: "static",
  // Bilingual: English at the root, Russian under /ru.
  i18n: {
    locales: ["en", "ru"],
    defaultLocale: "en",
    routing: { prefixDefaultLocale: false },
  },
  integrations: [icon(), sitemap()],
  vite: {
    plugins: [tailwindcss()],
  },
});
