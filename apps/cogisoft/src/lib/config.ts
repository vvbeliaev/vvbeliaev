import type { Lang, UIKey } from "$i18n/ui";

/** Copy that differs per locale. */
type Localized = Record<Lang, string>;

export const SITE = {
  name: "Cogisoft",
  url: "https://cogisoft.dev",
  // TODO: hello@cogisoft.dev is unverified — the primary CTA points at Telegram
  // (known-working) until the mailbox is confirmed. Swap CONTACT_HREF back then.
  email: "hello@cogisoft.dev",
  telegram: "https://t.me/vvbeliaevv",
  // The person behind it. The link is deliberate: the two brands are connected
  // openly, never firewalled — a hidden link reads worse than a stated one.
  founder: "Vladimir Beliaev",
  founderUrl: "https://vvbeliaev.dev",
} as const;

export const CONTACT_HREF = SITE.telegram;

// Per-locale site metadata (meta description / Intl locale).
export const SITE_I18N: Record<Lang, { tagline: string; description: string; locale: string }> = {
  en: {
    tagline: "build the solution, then run it",
    description:
      "Cogisoft — I build the tech a business needs (funnel, app, internal tool, optimisation) and stay on to run it. Phase 1: build. Phase 2: operate, monthly, against an SLA.",
    locale: "en-US",
  },
  ru: {
    tagline: "собираю решение и веду его",
    description:
      "Cogisoft — собираю тех-решение под задачу бизнеса (воронка, приложение, внутренний инструмент, оптимизация) и остаюсь его вести. Фаза 1 — сборка. Фаза 2 — веду ежемесячно, под SLA.",
    locale: "ru-RU",
  },
};

// Root nav. Anchors only exist on pages that render the matching section, so
// nav items carry absolute paths and the offer page owns its own anchors.
export const NAV: ReadonlyArray<{ key: UIKey; href: string }> = [
  { key: "nav.phases", href: "/#phases" },
  { key: "nav.offers", href: "/#offers" },
];

/**
 * Offers. Each is a fixed scope of capabilities aimed at one audience's pain —
 * not a service listing. New entries appear only once a case backs them.
 */
export const OFFERS: ReadonlyArray<{
  slug: string;
  name: Localized;
  pain: Localized;
  promise: Localized;
  status: "proto" | "live";
}> = [
  {
    slug: "signals",
    name: {
      en: "Signals: demand before code",
      ru: "Сигналы: спрос до кода",
    },
    pain: {
      en: "You are about to build something nobody has paid for yet.",
      ru: "Вы собираетесь строить то, за что пока никто не заплатил.",
    },
    promise: {
      en: "Five gates in real traffic. Each ends with evidence — or an honest stop.",
      ru: "Пять ворот в реальном трафике. Каждые заканчиваются доказательством — или честной остановкой.",
    },
    status: "proto",
  },
];

/**
 * Cases. Empty by design: pages follow cases, never the other way round. The
 * section does not render until this has entries.
 */
export const CASES: ReadonlyArray<{
  name: string;
  tag: Localized;
  result: Localized;
  href?: string;
}> = [];

// The five funnel stages of the `signals` offer. Mono labels
// (`STAGE 00 · DISCOVERY`) are a brand ritual and stay English in both locales;
// card copy is translated via the `stage.<key>.*` i18n keys. `density` drives
// the dot-cluster indicator — audience accumulates as the funnel deepens.
export const STAGES = [
  {
    id: "00",
    key: "discovery",
    name: "DISCOVERY",
    density: 3,
    icons: ["ph:binoculars", "ph:chart-scatter", "ph:crosshair"],
  },
  {
    id: "01",
    key: "offer",
    name: "OFFER",
    density: 6,
    icons: ["ph:cursor-click", "ph:megaphone", "ph:credit-card"],
  },
  {
    id: "02",
    key: "attention",
    name: "ATTENTION",
    density: 10,
    icons: ["simple-icons:tiktok", "simple-icons:youtube", "simple-icons:instagram"],
  },
  {
    id: "03",
    key: "community",
    name: "COMMUNITY",
    density: 16,
    icons: ["simple-icons:telegram", "simple-icons:discord"],
  },
  {
    id: "04",
    key: "mvp",
    name: "MVP",
    density: 26,
    icons: ["ph:code", "ph:coins", "ph:arrows-clockwise"],
  },
] as const;

export type Stage = (typeof STAGES)[number];
