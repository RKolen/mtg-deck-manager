# Design Constraints

Placeholder for a future design system. Notes on hard constraints discovered during development.

---

## Data Scale

- ~108,000 mtg_card nodes in Drupal.
- Drupal JSON:API hard-caps pages at 50 items. Fetching all cards at build time is not viable (~2 hours).
- The collection page uses runtime paginated fetching with server-side filters (name, type, CMC, colors).

## Caching Strategy (to define)

- Client-side: React Query is already in place. `staleTime` / `cacheTime` should be tuned per query.
- Consider a pre-built card index (e.g. a nightly Gatsby build that writes a static JSON manifest of all card IDs + names) so autocomplete can work offline without hitting the API.
- Drupal internal page cache and dynamic page cache are active. JSON:API responses are cached by Drupal's cache tags.
- For the collection page, a service worker or IndexedDB cache for the card catalog would eliminate repeated API round trips between sessions.

## Layout / UI

- Collection page: sidebar left (filters), card grid center, stats panel right.
- Card images: Scryfall CDN URIs stored in field_image_uri. No local copies.
- Mobile breakpoints: not yet defined.

## Component Patterns

- CardModal: expects flat CardData interface. When sourcing from JSON:API (JsonApiResource), spread attributes + id before passing.
- CardFilter: onChange receives the full filter object, not a setter directly.

## Known Limitations

- No authentication on the frontend yet. JSON:API is read-only public; collection mutations (quantity changes) go through a custom REST or JSON:API PATCH endpoint (to be secured).
- No offline support yet.
