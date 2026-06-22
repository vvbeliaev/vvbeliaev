import type { Lang, UIKey } from "$i18n/ui";

export const SITE = {
  title: "Vladimir Beliaev",
  author: "Vladimir Beliaev",
  // TODO: set the final domain
  url: "https://vbeliaev.dev",
} as const;

// Per-locale site metadata (tagline / meta description / Intl locale).
export const SITE_I18N: Record<
  Lang,
  { tagline: string; description: string; locale: string; now: string }
> = {
  en: {
    tagline: "AI Full Stack Engineer · Product Lead · Analytics Engineer",
    description:
      "Personal site and long-form blog by Vladimir Beliaev — notes on AI, product and analytics.",
    locale: "en-US",
    now: "Lead engineer at Space N Place (Dubai PropTech)", // TODO: keep current
  },
  ru: {
    tagline: "AI Full Stack инженер · Product Lead · Analytics Engineer",
    description:
      "Личный сайт и блог Владимира Беляева — заметки про AI, продукт и аналитику.",
    locale: "ru-RU",
    now: "Ведущий разработчик в Space N Place (PropTech, Дубай)", // TODO: держать актуальным
  },
};

// Nav items reference translation keys + root-relative paths (localized at render).
export const NAV: ReadonlyArray<{ key: UIKey; href: string }> = [
  { key: "nav.home", href: "/" },
  { key: "nav.blog", href: "/blog" },
];

type Channel = {
  label: string;
  handle: string;
  href: string;
  primary?: boolean;
};

// FOLLOW — where to consume the content (the primary CTA for a content brand).
export const FOLLOW: ReadonlyArray<Channel> = [
  { label: "Telegram", handle: "@vvbeliaev_ch", href: "https://t.me/vvbeliaev_ch", primary: true },
  { label: "YouTube", handle: "@vvbeliaev", href: "https://www.youtube.com/@vvbeliaev" },
];

// CONNECT — how to reach out (secondary). Telegram DM is the preferred channel.
export const CONNECT: ReadonlyArray<Channel> = [
  { label: "Telegram", handle: "@vvbeliaev_me", href: "https://t.me/vvbeliaev_me", primary: true },
  { label: "GitHub", handle: "vvbeliaev", href: "https://github.com/vvbeliaev" },
  { label: "Email", handle: "vvladimirbeliaev@gmail.com", href: "mailto:vvladimirbeliaev@gmail.com" },
  { label: "Resume", handle: "rxresu.me", href: "https://rxresu.me/vvbeliaev/full-stack" },
];

type Project = {
  name: string;
  tag: string;
  description: string;
  href: string;
  featured?: boolean;
  highlights?: readonly string[];
};

// Selected work shown on the home page. `featured` gets the accent treatment.
export const PROJECTS: ReadonlyArray<Project> = [
  {
    name: "Space N Place",
    tag: "Lead Engineer · Dubai PropTech",
    description:
      "AI real-estate discovery & market intelligence for Dubai.", // TODO: confirm wording
    href: "https://spacenplace.ai",
    featured: true,
    highlights: [
      "Live Dubai market snapshot",
      "ML liquidity scoring",
      "Multimodal vector search",
      "Floor-plan understanding",
    ],
  },
  {
    name: "LLM-Агент",
    tag: "AI agents for business",
    description:
      "Turns company knowledge into 24/7 RAG assistants across web, Telegram & Bitrix24.",
    href: "https://llmagent.ru",
  },
];

// Parked: earlier micro-SaaS, currently lower priority. Re-add to PROJECTS when
// the next products ship.
export const ARCHIVED_PROJECTS: ReadonlyArray<Project> = [
  {
    name: "Quizbee",
    tag: "Founder",
    description: "Turns PDFs and lecture notes into interactive quizzes.",
    href: "https://quizbee.academy",
  },
  {
    name: "HackSeeker",
    tag: "Founder",
    description: "LLM-powered market-validation tool for product ideas.",
    href: "https://hackseeker.com",
  },
  {
    name: "YouStory",
    tag: "Founder",
    description: "Interactive AI storytelling with branching narratives.",
    href: "https://ys.cogitosoftware.nl",
  },
];
