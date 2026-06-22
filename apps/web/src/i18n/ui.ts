// UI string dictionaries. Keep keys flat and stable; add a key to BOTH locales.
// Used via the helpers in ./utils.ts — never hardcode UI copy in components.

export const languages = {
  en: "English",
  ru: "Русский",
} as const;

export type Lang = keyof typeof languages;

export const defaultLang: Lang = "en";

export const ui = {
  en: {
    "nav.home": "Home",
    "nav.blog": "Articles",
    "lang.switch": "RU",
    "hero.intro":
      "I write long-form posts on AI, product and analytics. This is a field log: numbered articles, breakdowns and by-the-numbers recaps.",
    "hero.cta": "Read the blog",
    "home.now": "Now",
    "home.work": "Selected work",
    "home.follow": "Follow",
    "home.connect": "Connect",
    "home.latest": "Latest articles",
    "blog.title": "Articles",
    "blog.subtitle": "Long-form articles, breakdowns and field notes.",
    "blog.empty": "No articles here yet — they're on the way.",
    "article.prefix": "Article",
    "post.min": "min read",
    "post.prev": "Previous",
    "post.next": "Next",
    "post.back": "← Back to the field log",
  },
  ru: {
    "nav.home": "Главная",
    "nav.blog": "Статьи",
    "lang.switch": "EN",
    "hero.intro":
      "Пишу лонгриды про AI, продукт и аналитику. Это полевой журнал: нумерованные статьи, разборы и сводки цифр.",
    "hero.cta": "Читать блог",
    "home.now": "Сейчас",
    "home.work": "Избранное",
    "home.follow": "Подписаться",
    "home.connect": "Связь",
    "home.latest": "Свежие статьи",
    "blog.title": "Статьи",
    "blog.subtitle": "Лонгриды, разборы и полевые заметки.",
    "blog.empty": "Здесь пока пусто — статьи в пути.",
    "article.prefix": "Статья",
    "post.min": "мин чтения",
    "post.prev": "Предыдущая",
    "post.next": "Следующая",
    "post.back": "← Назад в field log",
  },
} as const;

export type UIKey = keyof (typeof ui)[typeof defaultLang];
