import type { Lang, UIKey } from "$i18n/ui";

/** Copy that differs per locale. Tech nouns stay untranslated — see STACK. */
type Localized = Record<Lang, string>;

export const SITE = {
  // Locale-neutral brand handle (used as a stable fallback). Displayed name is
  // locale-aware — see SITE_I18N[lang].name.
  title: "Vladimir Beliaev",
  author: "Vladimir Beliaev",
  // Cross-channel handle (github/youtube/telegram). Shown as the header wordmark.
  handle: "vvbeliaev",
  url: "https://vvbeliaev.dev",
  // Social preview image (absolute path under public/).
  ogImage: "/avatar.jpg",
} as const;

// Availability. Drives the hero status LED — flip to false when not looking.
export const OPEN_TO_WORK = true;

// Per-locale site identity. `role` is the single hire-legible title; `pitch` is
// the reason to hire it; `facts` is the line a recruiter scans first.
export const SITE_I18N: Record<
  Lang,
  {
    name: string;
    role: string;
    pitch: string;
    facts: string;
    description: string;
    locale: string;
  }
> = {
  en: {
    name: "Vladimir Beliaev",
    role: "AI Full Stack Engineer",
    pitch:
      "One person covering product, engineering and data. For a small team, that's the whole tech side.",
    facts: "Yerevan · Remote · English C1",
    description:
      "Vladimir Beliaev — AI Full Stack Engineer. Ships AI products end-to-end: product, engineering, data, infrastructure. Open to roles and contract work.",
    locale: "en-US",
  },
  ru: {
    name: "Владимир Беляев",
    role: "AI Full Stack Engineer",
    pitch:
      "Один человек закрывает продукт, инженерию и данные. Для небольшой команды это вся техчасть.",
    facts: "Ереван · Remote · English C1",
    description:
      "Владимир Беляев — AI Full Stack Engineer. Довожу AI-продукты от идеи до прода: продукт, инженерия, данные, инфраструктура. Открыт к ролям и подрядной работе.",
    locale: "ru-RU",
  },
};

// Nav items reference translation keys + root-relative paths (localized at render).
export const NAV: ReadonlyArray<{ key: UIKey; href: string }> = [
  { key: "nav.home", href: "/" },
  { key: "nav.about", href: "/about" },
  { key: "nav.blog", href: "/blog" },
];

type Channel = {
  label: string;
  handle: string;
  href: string;
  primary?: boolean;
};

// FOLLOW — where to consume the content. Secondary to hiring: rendered last.
export const FOLLOW: ReadonlyArray<Channel> = [
  { label: "Telegram", handle: "@vvbeliaevv_ch", href: "https://t.me/vvbeliaevv_ch", primary: true },
  { label: "YouTube", handle: "@vvbeliaev", href: "https://www.youtube.com/@vvbeliaev" },
];

// CONNECT — how to reach out. Telegram DM is the preferred channel and the
// destination of the hero CTA (and of every "CV on request" link).
export const CONNECT: ReadonlyArray<Channel> = [
  { label: "Telegram", handle: "@vvbeliaevv", href: "https://t.me/vvbeliaevv", primary: true },
  { label: "GitHub", handle: "vvbeliaev", href: "https://github.com/vvbeliaev" },
  { label: "Email", handle: "vvbeliaevv@gmail.com", href: "mailto:vvbeliaevv@gmail.com" },
];

export const CONTACT_HREF =
  CONNECT.find((c) => c.primary)?.href ?? CONNECT[0].href;

/**
 * `kind` splits employment from own ventures — the distinction a hiring reader
 * needs and cannot infer from the tag alone.
 */
type Project = {
  name: string;
  kind: "role" | "own";
  tag: Localized;
  description: Localized;
  href: string;
  featured?: boolean;
  highlights?: ReadonlyArray<Localized>;
};

// Selected work shown on the home page, grouped by `kind`. `featured` entries
// get the accent log row (see Work.astro); the rest land in the compact list.
export const PROJECTS: ReadonlyArray<Project> = [
  {
    name: "Space N Place",
    kind: "role",
    tag: {
      en: "Data Engineer / Full Stack · Dubai PropTech",
      ru: "Data Engineer / Full Stack · PropTech Дубая",
    },
    description: {
      en: "AI real-estate discovery & market intelligence for Dubai.",
      ru: "AI-поиск недвижимости и рыночная аналитика по Дубаю.",
    },
    href: "https://spacenplace.ai",
    featured: true,
    highlights: [
      { en: "Live Dubai market snapshot", ru: "Живой срез рынка Дубая" },
      { en: "ML liquidity scoring", ru: "ML-скоринг ликвидности" },
      { en: "Multimodal vector search", ru: "Мультимодальный векторный поиск" },
      { en: "Floor-plan understanding", ru: "Разбор планировок" },
    ],
  },
  {
    name: "Cogisoft",
    kind: "own",
    tag: {
      en: "Project & contract work",
      ru: "Проектная и подрядная работа",
    },
    description: {
      en: "Where my project and contract work lives — offers, cases, write-ups.",
      ru: "Куда складываю проектную и подрядную работу — офферы, кейсы, разборы.",
    },
    href: "https://cogisoft.dev",
  },
];

// On hold: kept out of the site until the role is public again. To bring it
// back, move this entry into PROJECTS above — nothing else changes.
export const PARKED_PROJECTS: ReadonlyArray<Project> = [
  {
    name: "TraffHub",
    kind: "role",
    tag: {
      en: "Lead Engineer · Media buying",
      ru: "Lead Engineer · Медиабаинг",
    },
    description: {
      en: "Internal product platform for a Tier-1 media-buying team: site, season leaderboard, story tooling.",
      ru: "Внутренняя продуктовая платформа медиабаинговой команды Tier-1: сайт, лидерборд сезона, инструмент для сторис.",
    },
    href: "https://traffhub.io",
    featured: true,
    highlights: [
      { en: "pnpm monorepo, CI → registry → Coolify", ru: "pnpm-монорепа, CI → registry → Coolify" },
      { en: "Live leaderboard from Google Sheets", ru: "Живой лидерборд из Google Sheets" },
      { en: "Telegram-bot login", ru: "Вход через Telegram-бота" },
      { en: "Design system across products", ru: "Единая дизайн-система" },
    ],
  },
];

// Parked: finished or lower-priority work. Not rendered — move an entry into
// PROJECTS when it's worth showing again.
export const ARCHIVED_PROJECTS: ReadonlyArray<Project> = [
  {
    name: "LLM-Агент",
    kind: "role",
    tag: {
      en: "Lead / Core Developer · 2023–2024",
      ru: "Lead / Core Developer · 2023–2024",
    },
    description: {
      en: "Self-hosted RAG assistants over company knowledge — web, Telegram, Bitrix24.",
      ru: "Self-hosted RAG-ассистенты по базе знаний компании — веб, Telegram, Bitrix24.",
    },
    href: "https://llmagent.ru",
  },
  {
    name: "Quizbee",
    kind: "own",
    tag: { en: "Founder", ru: "Основатель" },
    description: {
      en: "Turns PDFs and lecture notes into interactive quizzes.",
      ru: "Превращает PDF и конспекты в интерактивные квизы.",
    },
    href: "https://quizbee.academy",
  },
];

/**
 * Stack for the About page. Tool names are proper nouns and stay as-is; only
 * the group label is localized.
 */
export const STACK: ReadonlyArray<{ label: Localized; items: readonly string[] }> = [
  {
    label: { en: "Languages", ru: "Языки" },
    items: ["TypeScript", "Python", "SQL", "Go", "Bash"],
  },
  {
    label: { en: "Frontend", ru: "Фронтенд" },
    items: ["SvelteKit", "Astro", "Next.js", "React", "Tailwind CSS"],
  },
  {
    label: { en: "Backend", ru: "Бэкенд" },
    items: ["FastAPI", "Node.js", "PostgreSQL", "Redis", "Qdrant", "Meilisearch"],
  },
  {
    label: { en: "AI", ru: "AI" },
    items: ["RAG", "LLM agents", "LangChain", "PydanticAI", "OpenAI API", "PyTorch"],
  },
  {
    label: { en: "Infrastructure", ru: "Инфраструктура" },
    items: ["Docker", "Kubernetes", "Terraform", "GitHub Actions", "Coolify", "Hetzner", "Linux"],
  },
  {
    label: { en: "Product & data", ru: "Продукт и данные" },
    items: ["Unit economics", "A/B testing", "ETL", "Metabase", "Superset"],
  },
];
