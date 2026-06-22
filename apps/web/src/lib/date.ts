import { SITE } from "./config";

export function formatDate(date: Date): string {
  return new Intl.DateTimeFormat(SITE.locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(date);
}
