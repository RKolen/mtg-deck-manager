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

/** Builds /cards/:slug with optional printing / deck-slot context. */
export function cardPrintingsPath(
  title: string,
  opts?: {
    printing?: string;
    deckId?: string;
    slotId?: string;
    from?: string;
  },
): string {
  const params = new URLSearchParams();
  if (opts?.printing != null && opts.printing !== '') {
    params.set('printing', opts.printing);
  }
  if (opts?.deckId != null && opts.deckId !== '') {
    params.set('deck', opts.deckId);
  }
  if (opts?.slotId != null && opts.slotId !== '') {
    params.set('slot', opts.slotId);
  }
  if (opts?.from != null && opts.from !== '') {
    params.set('from', opts.from);
  }
  const query = params.toString();
  return `/cards/${slugify(title)}${query !== '' ? `?${query}` : ''}`;
}
