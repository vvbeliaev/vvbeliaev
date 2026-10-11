import DOMPurify from 'dompurify';
import { marked } from 'marked';

// `[[people/anna]]` и `[[people/anna|Аня]]` — ссылки на страницы.
const LINK = /\[\[([a-z0-9-]+\/[a-z0-9-]+)(?:\|([^\]\n]{0,120}))?\]\]/g;

// Часть текста здесь чужая: пересланное и сохранённое с веба. Картинки и встраивания
// выключены — чтение записи не должно ходить на чужой сервер.
const FORBIDDEN = ['img', 'picture', 'source', 'video', 'audio', 'iframe', 'object', 'embed', 'form', 'input', 'style'];

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node instanceof HTMLAnchorElement && !node.getAttribute('href')?.startsWith('#')) {
    node.setAttribute('target', '_blank');
    node.setAttribute('rel', 'noopener noreferrer');
  }
});

/** `breaks` — для записей, где перевод строки значит перевод строки: слова владельца, факты. */
export function render(text: string, breaks = false): string {
  const linked = text.replace(LINK, (_all, target: string, label?: string) => `[${label ?? target}](#/pages/${target}.md)`);
  return DOMPurify.sanitize(marked.parse(linked, { async: false, gfm: true, breaks }), { FORBID_TAGS: FORBIDDEN });
}
