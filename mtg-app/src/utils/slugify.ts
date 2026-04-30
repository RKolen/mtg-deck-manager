/**
 * Converts a card or deck title into a URL-safe slug.
 *
 * Rules:
 *  - Lowercase everything.
 *  - Strip apostrophes and curly-quote variants so possessives collapse
 *    cleanly (e.g. "Jace's" -> "jaces").
 *  - Replace any run of non-alphanumeric characters with a single dash.
 *  - Trim leading/trailing dashes.
 */
export function slugify(title: string): string {
  return title
    .toLowerCase()
    .replace(/[''`]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}
