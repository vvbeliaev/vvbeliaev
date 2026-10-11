import DOMPurify from 'dompurify';
import { marked } from 'marked';

// `[[people/anna]]` и `[[people/anna|Аня]]` — ссылки на страницы.
const LINK = /\[\[([a-z0-9-]+\/[a-z0-9-]+)(?:\|([^\]\n]{0,120}))?\]\]/g;

// Часть текста здесь чужая: пересланное и сохранённое с веба. Чтение записи не должно ходить
// на чужой сервер, поэтому убрано всё, что грузит ресурс: картинки, встраивания, SVG, стили.
// Сервер отдаёт сайт ещё и со строгой политикой содержимого, но `make web-dev` идёт без неё.
const FORBID_TAGS = [
  'img', 'picture', 'source', 'video', 'audio', 'track', 'iframe', 'object', 'embed',
  'svg', 'math', 'style', 'link', 'meta', 'base', 'form', 'input', 'button',
];
const FORBID_ATTR = ['style', 'background', 'poster', 'srcset', 'ping'];
// Ссылки — обычные адреса, почта, якоря и пути этого же сайта.
const ALLOWED_URI_REGEXP = /^(?:https?:|mailto:|#|\/)/i;

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node instanceof HTMLAnchorElement && !node.getAttribute('href')?.startsWith('#')) {
    node.setAttribute('target', '_blank');
    node.setAttribute('rel', 'noopener noreferrer');
  }
});

/** `breaks` — для записей, где перевод строки значит перевод строки: слова владельца, факты. */
export function render(text: string, breaks = false): string {
  const linked = text.replace(LINK, (_all, target: string, label?: string) => `[${label ?? target}](#/pages/${target}.md)`);
  const html = marked.parse(linked, { async: false, gfm: true, breaks });
  return DOMPurify.sanitize(html, { FORBID_TAGS, FORBID_ATTR, ALLOWED_URI_REGEXP });
}
