import { ui, defaultLang, languages, type Lang, type UIKey } from "./ui";

const isLang = (value: string): value is Lang => value in languages;

/** Detect the active locale from the URL path (`/ru/...` → "ru", else default). */
export function getLangFromUrl(url: URL): Lang {
  const [, first] = url.pathname.split("/");
  return isLang(first) ? first : defaultLang;
}

/** Translation function bound to a locale, falling back to the default locale. */
export function useTranslations(lang: Lang) {
  return function t(key: UIKey): string {
    return ui[lang][key] ?? ui[defaultLang][key];
  };
}

/** Prefix a root-relative path with the locale (default locale stays at root). */
export function localizePath(path: string, lang: Lang): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  if (lang === defaultLang) return clean;
  return clean === "/" ? `/${lang}` : `/${lang}${clean}`;
}

/** Strip any locale prefix from a path, returning the canonical root-relative path. */
export function stripLangPrefix(pathname: string): string {
  const [, first, ...rest] = pathname.split("/");
  if (isLang(first)) return `/${rest.join("/")}`;
  return pathname;
}

/** The equivalent path in another locale, for a language switcher. */
export function getAlternatePath(url: URL, target: Lang): string {
  return localizePath(stripLangPrefix(url.pathname), target);
}

export const otherLang = (lang: Lang): Lang => (lang === "en" ? "ru" : "en");
