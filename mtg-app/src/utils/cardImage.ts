/**
 * Resolve card art URL. Prefer Drupal-local media when present, then
 * Scryfall CDN URI from the catalog. Never use Scryfall named redirects.
 */
export function cardImageSrc(card: {
  field_image_local?: { url?: string | null } | null;
  field_image_uri?: string | null;
}): string {
  const local = card.field_image_local?.url;
  if (local) {
    return local;
  }
  if (card.field_image_uri) {
    return card.field_image_uri;
  }
  return '/placeholder-card.svg';
}
