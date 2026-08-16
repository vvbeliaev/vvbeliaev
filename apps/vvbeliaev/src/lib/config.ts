import type { Lang, UIKey } from "$i18n/ui";

export const SITE = {
  // Locale-neutral brand handle (used as a stable fallback). Displayed name is
  // locale-aware — see SITE_I18N[lang].name.
  title: "Vladimir Beliaev",
  author: "Vladimir Beliaev",
  // Cross-channel handle (github/youtube/telegram). Shown as the header wordmark.
  handle: "vvbeliaev",
  url: "https://vvbeliaev.dev",
} as const;

// Per-locale site metadata (display name / tagline / meta description / Intl locale).
export const SITE_I18N: Record<
  Lang,
  { name: string; tagline: string; description: string; locale: string }
> = {
  en: {
    name: "Vladimir Beliaev",
    tagline: "AI Full Stack Engineer · Product Lead · Analytics Engineer",
    description:
      "Personal site and long-form blog by Vladimir Beliaev — notes on AI, product and analytics.",
    locale: "en-US",
  },
  ru: {
    name: "Владимир Беляев",
    tagline: "AI Full Stack инженер · Product Lead · Analytics Engineer",
    description:
      "Личный сайт и блог Владимира Беляева — заметки про AI, продукт и аналитику.",
    locale: "ru-RU",
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
  { label: "Telegram", handle: "@vvbeliaevv_ch", href: "https://t.me/vvbeliaevv_ch", primary: true },
  { label: "YouTube", handle: "@vvbeliaev", href: "https://www.youtube.com/@vvbeliaev" },
];

// CONNECT — how to reach out (secondary). Telegram DM is the preferred channel.
export const CONNECT: ReadonlyArray<Channel> = [
  { label: "Telegram", handle: "@vvbeliaevv", href: "https://t.me/vvbeliaevv", primary: true },
  { label: "GitHub", handle: "vvbeliaev", href: "https://github.com/vvbeliaev" },
  { label: "Email", handle: "vvbeliaevv@gmail.com", href: "mailto:vvbeliaevv@gmail.com" },
];

type Project = {
  name: string;
  tag: string;
  description: string;
  href: string;
  featured?: boolean;
  highlights?: readonly string[];
};

// Selected work shown on the home page. `featured` entries get the accent log
// row (see Work.astro); everything else lands in the compact list below it.
export const PROJECTS: ReadonlyArray<Project> = [
  {
    name: "Space N Place",
    tag: "Lead Engineer · Dubai PropTech",
    description:
      "AI real-estate discovery & market intelligence for Dubai.",
    href: "https://spacenplace.ai",
    featured: true,
    highlights: [
      "Live Dubai market snapshot",
      "ML liquidity scoring",
      "Multimodal vector search",
      "Floor-plan understanding",
    ],
  },
];

// On hold: kept out of the site until the role is public again. To bring it
// back, move this entry into PROJECTS above — nothing else changes.
export const PARKED_PROJECTS: ReadonlyArray<Project> = [
  {
    name: "TraffHub",
    tag: "Lead Engineer · Media buying",
    description:
      "Internal product platform for a Tier-1 media-buying team: site, season leaderboard, story tooling.",
    href: "https://traffhub.io",
    featured: true,
    highlights: [
      "pnpm monorepo, CI → registry → Coolify",
      "Live leaderboard from Google Sheets",
      "Telegram-bot login",
      "Design system across products",
    ],
  },
];

// Earlier micro-SaaS: shipped, now low-priority. Rendered as the compact list
// under the featured entries.
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
