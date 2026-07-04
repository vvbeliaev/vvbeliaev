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
    "nav.blog": "Blog",
    "lang.aria": "Switch language",
    "lang.to.en": "Switch to English",
    "lang.to.ru": "Переключить на русский",
    "menu.open": "Open menu",
    "menu.close": "Close menu",
    "hero.intro":
      "I write long-form posts on AI, product and analytics. This is a field log: numbered articles, breakdowns and by-the-numbers recaps.",
    "hero.cta": "Read the blog",
    "hero.subtitle":
      "An engineer mapping the space between code, product, and market.",
    "facet.engineer.name": "Engineer",
    "facet.engineer.caption": "ship AI products end-to-end",
    "facet.product.name": "Product",
    "facet.product.caption": "decide what's worth building",
    "facet.analytics.name": "Analytics",
    "facet.analytics.caption": "read the market with data",
    "notfound.title": "Page not found",
    "notfound.body": "This page doesn't exist or has moved.",
    "notfound.back": "Back home",
    "home.now": "Now",
    "home.work": "Selected work",
    "home.follow": "Follow",
    "home.connect": "Connect",
    "home.latest": "Latest articles",
    "blog.title": "Articles",
    "blog.subtitle": "Long-form articles, breakdowns and field notes.",
    "blog.empty": "No notes here yet — the first ones are on the way.",
    "blog.soon": "Soon",
    "article.prefix": "Article",
    "post.min": "min read",
    "post.prev": "Previous",
    "post.next": "Next",
    "post.back": "← Back to the field log",
    "post.translated.ru": "Translated from the Russian original",
    "post.translated.en": "Translated from the English original",
    "post.original": "read the original",
  },
  ru: {
    "nav.home": "Главная",
    "nav.blog": "Блог",
    "lang.aria": "Сменить язык",
    "lang.to.en": "Switch to English",
    "lang.to.ru": "Переключить на русский",
    "menu.open": "Открыть меню",
    "menu.close": "Закрыть меню",
    "hero.intro":
      "Пишу лонгриды про AI, продукт и аналитику. Это полевой журнал: нумерованные статьи, разборы и сводки цифр.",
    "hero.cta": "Читать блог",
    "hero.subtitle":
      "Инженер, который наносит на карту пространство между кодом, продуктом и рынком.",
    "facet.engineer.name": "Инженер",
    "facet.engineer.caption": "довожу AI-продукты от идеи до релиза",
    "facet.product.name": "Продукт",
    "facet.product.caption": "решаю, что вообще стоит строить",
    "facet.analytics.name": "Аналитика",
    "facet.analytics.caption": "читаю рынок через данные",
    "notfound.title": "Страница не найдена",
    "notfound.body": "Такой страницы нет или она переехала.",
    "notfound.back": "На главную",
    "home.now": "Сейчас",
    "home.work": "Избранное",
    "home.follow": "Подписаться",
    "home.connect": "Связь",
    "home.latest": "Свежие статьи",
    "blog.title": "Статьи",
    "blog.subtitle": "Лонгриды, разборы и полевые заметки.",
    "blog.empty": "Здесь пока пусто — первые заметки в пути.",
    "blog.soon": "Скоро",
    "article.prefix": "Статья",
    "post.min": "мин чтения",
    "post.prev": "Предыдущая",
    "post.next": "Следующая",
    "post.back": "← Назад в field log",
    "post.translated.ru": "Перевод с русского оригинала",
    "post.translated.en": "Перевод с английского оригинала",
    "post.original": "читать оригинал",
  },
} as const;

export type UIKey = keyof (typeof ui)[typeof defaultLang];
