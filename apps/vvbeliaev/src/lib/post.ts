import type { CollectionEntry } from "astro:content";

/**
 * Canonical slug for a blog post.
 *
 * Folder-per-article entries have ids like `note-14-slug/ru`; we strip the
 * trailing language segment so the locale lives only in the route prefix
 * (`/blog/note-14-slug`, `/ru/blog/note-14-slug`) and never doubles up in the
 * URL. Flat legacy notes (`note-01-...`) pass through unchanged.
 *
 * Because both language versions share this slug, the other-language URL of a
 * post is just `localizePath(`/blog/${postSlug(post)}`, otherLang)`.
 */
export function postSlug(post: CollectionEntry<"blog">): string {
  return post.id.replace(/\/(ru|en)$/, "");
}
