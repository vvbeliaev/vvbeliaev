import { SITE_I18N } from "./config";
import type { Lang } from "$i18n/ui";

export function formatDate(date: Date, lang: Lang): string {
  return new Intl.DateTimeFormat(SITE_I18N[lang].locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(date);
}
