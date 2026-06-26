import { defineCollection } from "astro:content";
import { z } from "astro:schema";
import { glob } from "astro/loaders";

const blog = defineCollection({
  // Лонгриды и «нумерованные заметки» в Markdown/MDX.
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/blog" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    // Locale of the post; English is the default.
    lang: z.enum(["en", "ru"]).default("en"),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    // Сквозной ритуал бренда — нумерация статей («Статья №14»).
    // Он же связывает RU↔EN-версии одной статьи.
    articleNumber: z.number().int().positive().optional(),
    // Если статья — перевод, указываем язык оригинала; в UI рендерится плашка
    // «Translated from …» со ссылкой на оригинал (тот же articleNumber/slug).
    translatedFrom: z.enum(["en", "ru"]).optional(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
    // Cover image: a path under /public (e.g. "/covers/note-01.jpg") or a URL.
    cover: z.string().optional(),
  }),
});

export const collections = { blog };
