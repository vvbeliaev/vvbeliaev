import type { Lang } from "$i18n/ui";

export const SITE = {
  name: "Cogisoft",
  url: "https://cogisoft.dev",
  // TODO: confirm the mailbox exists before launch (or switch to another address)
  email: "hello@cogisoft.dev",
} as const;

// Per-locale site metadata (meta description / Intl locale).
export const SITE_I18N: Record<Lang, { description: string; locale: string }> = {
  en: {
    description:
      "Cogisoft — a market-first studio. We validate demand with live experiments and build only what the market confirmed.",
    locale: "en-US",
  },
  ru: {
    description:
      "Cogisoft — market-first студия. Проверяем спрос живыми экспериментами и строим только то, что рынок подтвердил.",
    locale: "ru-RU",
  },
};

// The five funnel stages. Mono labels (`STAGE 00 · DISCOVERY`) are a brand
// ritual and stay English in both locales; card copy is translated via the
// `stage.<key>.*` i18n keys. `density` drives the dot-cluster indicator —
// audience accumulates as the funnel deepens.
export const STAGES = [
  { id: "00", key: "discovery", name: "DISCOVERY", density: 3 },
  { id: "01", key: "offer", name: "OFFER", density: 6 },
  { id: "02", key: "attention", name: "ATTENTION", density: 10 },
  { id: "03", key: "community", name: "COMMUNITY", density: 16 },
  { id: "04", key: "mvp", name: "MVP", density: 26 },
] as const;

export type Stage = (typeof STAGES)[number];
