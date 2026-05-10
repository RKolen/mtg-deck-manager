/**
 * Typed JSON:API client for the MTG Deck Manager Drupal backend.
 *
 * All mutations go through this module. Build-time card data is handled by
 * gatsby-source-drupal + GraphQL; this client handles everything dynamic:
 * decks, collection quantities, and deck-card relationships.
 */

import type { AxiosInstance } from 'axios';
import type {
  CollectionCardAttributes,
  DeckAttributes,
  DeckCardWithCard,
  JsonApiCollectionResponse,
  JsonApiResource,
  JsonApiResourceIdentifier,
  JsonApiSingleResponse,
  MtgCardAttributes,
} from '../types/drupal';
import { createDrupalClient } from './httpClient';
import { slugify } from '../utils/slugify';

const client: AxiosInstance = createDrupalClient('/jsonapi', {
  'Content-Type': 'application/vnd.api+json',
  Accept: 'application/vnd.api+json',
});

// ---------------------------------------------------------------------------
// Generic helpers
// ---------------------------------------------------------------------------

/**
 * Follows JSON:API pagination and returns all resources from a collection.
 */
async function fetchAll<T>(url: string): Promise<JsonApiResource<T>[]> {
  const results: JsonApiResource<T>[] = [];
  let next: string | null = url;

  while (next !== null) {
    const response: { data: JsonApiCollectionResponse<T> } = await client.get<JsonApiCollectionResponse<T>>(next);
    results.push(...response.data.data);
    next = response.data.links.next?.href ?? null;
  }

  return results;
}

// ---------------------------------------------------------------------------
// MTG Card
// ---------------------------------------------------------------------------

const CARD_FIELDS =
  'title,field_mana_cost,field_cmc,field_type_line,field_colors,field_color_identity,' +
  'field_oracle_text,field_image_uri,field_is_mana_producer,field_produced_mana,' +
  'field_legal_formats,field_price_usd,field_price_usd_foil,field_set_code,' +
  'field_set_name,field_rarity,field_collector_number';

// Full field set used on the card detail page — includes P/T and loyalty.
const CARD_DETAIL_FIELDS =
  CARD_FIELDS + ',field_power,field_toughness,field_loyalty';

export interface CardPage {
  cards: JsonApiResource<MtgCardAttributes>[];
  nextUrl: string | null;
}

/**
 * Fetches one page of mtg_card nodes with optional filters.
 * Pass the returned nextUrl as `pageUrl` to get the next page.
 */
export async function fetchCardsPage(
  pageUrl: string | null,
  filters: {
    name?: string;
    colors?: string[];
    type?: string;
    maxCmc?: number | null;
  } = {},
): Promise<CardPage> {
  const url = pageUrl ?? '/node/mtg_card';
  const params: Record<string, string> = {};

  if (pageUrl === null) {
    // First page — apply filters and field selection.
    params['fields[node--mtg_card]'] = CARD_FIELDS;
    params['filter[status][value]'] = '1';
    params['page[limit]'] = '50';

    if (filters.name != null && filters.name !== '') {
      params['filter[title][operator]'] = 'CONTAINS';
      params['filter[title][value]'] = filters.name;
    }
    if (filters.type != null && filters.type !== 'All') {
      params['filter[field_type_line][operator]'] = 'CONTAINS';
      params['filter[field_type_line][value]'] = filters.type;
    }
    if (filters.maxCmc != null) {
      params['filter[field_cmc][operator]'] = '<=';
      params['filter[field_cmc][value]'] = String(filters.maxCmc);
    }
    if (filters.colors != null && filters.colors.length > 0) {
      filters.colors.forEach((color, i) => {
        params[`filter[colors][condition][path]`] = 'field_colors';
        params[`filter[colors][condition][operator]`] = 'IN';
        params[`filter[colors][condition][value][${i}]`] = color;
      });
    }
  }

  const response = await client.get<JsonApiCollectionResponse<MtgCardAttributes>>(
    url,
    { params: pageUrl !== null ? {} : params },
  );

  return {
    cards: response.data.data,
    nextUrl: response.data.links.next?.href ?? null,
  };
}

/**
 * Fetches a single card whose title slugifies to the given slug.
 *
 * Strategy: use the first word of the slug as a STARTS_WITH filter to
 * narrow the result set to at most 50 records, then find the exact slug
 * match client-side. This avoids needing Drupal path aliases for 108k nodes.
 */
export async function fetchCardBySlug(
  slug: string,
): Promise<JsonApiResource<MtgCardAttributes> | null> {
  const firstWord = slug.split('-')[0] ?? slug;
  // If the first slug word ends in 's', it may be due to a possessive
  // apostrophe being stripped (e.g. "Prey's" -> "preys"). Removing the
  // trailing 's' gives a prefix that matches the original title.
  const prefixWord =
    firstWord.endsWith('s') && firstWord.length > 2
      ? firstWord.slice(0, -1)
      : firstWord;
  const searchPrefix =
    prefixWord.charAt(0).toUpperCase() + prefixWord.slice(1);

  const response = await client.get<JsonApiCollectionResponse<MtgCardAttributes>>(
    '/node/mtg_card',
    {
      params: {
        'filter[title][operator]': 'STARTS_WITH',
        'filter[title][value]': searchPrefix,
        'fields[node--mtg_card]': CARD_DETAIL_FIELDS,
        'page[limit]': '50',
      },
    },
  );

  return (
    response.data.data.find(c => slugify(c.attributes.title) === slug) ?? null
  );
}

/**
 * Searches cards by name using a JSON:API filter. Used during XLSX import
 * to match card names to existing Drupal nodes.
 */
export async function findCardsByName(
  name: string,
): Promise<JsonApiResource<MtgCardAttributes>[]> {
  const response = await client.get<JsonApiCollectionResponse<MtgCardAttributes>>(
    '/node/mtg_card',
    {
      params: {
        'filter[title]': name,
        'fields[node--mtg_card]': CARD_FIELDS,
      },
    },
  );
  return response.data.data;
}

// ---------------------------------------------------------------------------
// Decks
// ---------------------------------------------------------------------------

export async function fetchDecks(): Promise<JsonApiResource<DeckAttributes>[]> {
  return fetchAll<DeckAttributes>(
    '/node/deck?fields[node--deck]=title,field_format,field_notes,drupal_internal__nid',
  );
}

/**
 * Fetches all decks and returns the one whose title slugifies to the given
 * slug, or null if no match is found.
 */
export async function fetchDeckBySlug(
  slug: string,
): Promise<JsonApiResource<DeckAttributes> | null> {
  const decks = await fetchDecks();
  return decks.find(d => slugify(d.attributes.title) === slug) ?? null;
}

export async function fetchDeck(
  id: string,
): Promise<JsonApiResource<DeckAttributes>> {
  const response = await client.get<JsonApiSingleResponse<DeckAttributes>>(
    `/node/deck/${id}`,
  );
  return response.data.data;
}

export async function createDeck(
  attributes: Pick<DeckAttributes, 'title' | 'field_format' | 'field_notes'>,
): Promise<JsonApiResource<DeckAttributes>> {
  const response = await client.post<JsonApiSingleResponse<DeckAttributes>>(
    '/node/deck',
    {
      data: {
        type: 'node--deck',
        attributes: { ...attributes, status: true },
      },
    },
  );
  return response.data.data;
}

export async function updateDeck(
  id: string,
  attributes: Partial<DeckAttributes>,
): Promise<JsonApiResource<DeckAttributes>> {
  const response = await client.patch<JsonApiSingleResponse<DeckAttributes>>(
    `/node/deck/${id}`,
    {
      data: {
        type: 'node--deck',
        id,
        attributes,
      },
    },
  );
  return response.data.data;
}

export async function deleteDeck(id: string): Promise<void> {
  await client.delete(`/node/deck/${id}`);
}

// ---------------------------------------------------------------------------
// Deck cards — paragraph--deck_card, owned by deck via field_deck_cards
//
// The DECK references its cards (deck → paragraph.deck_card → mtg_card).
// Each paragraph has field_card, field_quantity, field_is_sideboard.
// No back-reference from card to deck — the same card can appear in any
// number of decks independently.
//
// Reads:    JSON:API include on the deck node
// Mutations: POST /api/deck-cards (DeckCardsResource) — handles paragraph
//            lifecycle inside Drupal, bypassing JSON:API access restrictions.
// ---------------------------------------------------------------------------

const DECK_CARD_FIELDS =
  'title,field_mana_cost,field_cmc,field_type_line,' +
  'field_colors,field_color_identity,field_oracle_text,field_image_uri,' +
  'field_is_mana_producer,field_produced_mana,field_legal_formats';

interface ParagraphDeckCardAttributes {
  field_quantity: number;
  field_is_sideboard: boolean;
}

const deckCardsClient = createDrupalClient('/api');

async function deckCardAction(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const res = await deckCardsClient.post<Record<string, unknown>>(
    '/deck-cards?_format=json',
    payload,
    { headers: { 'Content-Type': 'application/json', Accept: 'application/json' } },
  );
  return res.data;
}

/**
 * Fetches all card slots for a deck by reading field_deck_cards paragraphs
 * and their referenced mtg_card nodes in a single JSON:API request.
 */
export async function fetchDeckCardsWithCards(
  deckId: string,
): Promise<DeckCardWithCard[]> {
  const response = await client.get<{
    data: JsonApiResource<Record<string, never>> & {
      relationships?: {
        field_deck_cards?: { data: Array<{ type: string; id: string }> };
      };
    };
    included?: JsonApiResource<Record<string, unknown>>[];
  }>(
    `/node/deck/${deckId}` +
    `?include=field_deck_cards,field_deck_cards.field_card` +
    `&fields[node--deck]=field_deck_cards` +
    `&fields[paragraph--deck_card]=field_card,field_quantity,field_is_sideboard` +
    `&fields[node--mtg_card]=${DECK_CARD_FIELDS}`,
  );

  const included = response.data.included ?? [];
  const cardMap = new Map<string, MtgCardAttributes & { id: string }>();
  const paraMap = new Map<string, JsonApiResource<ParagraphDeckCardAttributes>>();

  for (const item of included) {
    if (item.type === 'node--mtg_card') {
      cardMap.set(item.id, { id: item.id, ...(item.attributes as unknown as MtgCardAttributes) });
    } else if (item.type === 'paragraph--deck_card') {
      paraMap.set(item.id, item as unknown as JsonApiResource<ParagraphDeckCardAttributes>);
    }
  }

  const paraRefs = response.data.data.relationships?.field_deck_cards?.data ?? [];

  return paraRefs.flatMap(ref => {
    const para = paraMap.get(ref.id);
    if (!para) return [];
    const cardRef = (para.relationships?.field_card?.data) as JsonApiResourceIdentifier | null;
    if (!cardRef) return [];
    const card = cardMap.get(cardRef.id);
    if (!card) return [];
    return [{
      id: para.id,
      quantity: para.attributes.field_quantity ?? 1,
      isSideboard: para.attributes.field_is_sideboard ?? false,
      card,
    }];
  });
}

/**
 * Bulk-imports cards into a deck. Calls the deck-cards endpoint once per
 * card so the import page can show per-card progress.
 * Deck cards are completely separate from collection_card nodes —
 * you can deck cards you don't own.
 */
export async function importCardToDeck(
  deckId: string,
  cards: { cardId: string; quantity: number; isSideboard: boolean; cardName: string }[],
): Promise<void> {
  for (const c of cards) {
    await deckCardAction({
      action: 'add',
      deckUuid: deckId,
      cardUuid: c.cardId,
      quantity: c.quantity,
      isSideboard: c.isSideboard,
    });
  }
}

/**
 * Adds one card to a deck. Increments the existing paragraph's quantity if
 * the card is already in the same zone; otherwise creates a new paragraph.
 */
export async function addCardToDeck(
  deckId: string,
  cardId: string,
  isSideboard = false,
  existingSlots: DeckCardWithCard[] = [],
  _cardName = '',
): Promise<void> {
  const existing = existingSlots.find(
    s => s.card.id === cardId && s.isSideboard === isSideboard,
  );

  if (existing != null) {
    await setCardQuantityInDeck(existing.id, existing.quantity + 1, deckId, existingSlots);
    return;
  }

  await deckCardAction({ action: 'add', deckUuid: deckId, cardUuid: cardId, quantity: 1, isSideboard });
}

/**
 * Updates the quantity on an existing paragraph--deck_card.
 * Removes the slot when quantity reaches 0.
 */
export async function setCardQuantityInDeck(
  slotId: string,
  quantity: number,
  deckId: string,
  allSlots: DeckCardWithCard[],
): Promise<void> {
  if (quantity <= 0) {
    await removeCardFromDeck(slotId, deckId, allSlots);
    return;
  }
  await deckCardAction({ action: 'update', deckUuid: deckId, paraUuid: slotId, quantity });
}

/**
 * Removes a card slot from the deck and deletes its paragraph.
 */
export async function removeCardFromDeck(
  slotId: string,
  deckId: string,
  _allSlots: DeckCardWithCard[],
): Promise<void> {
  await deckCardAction({ action: 'remove', deckUuid: deckId, paraUuid: slotId });
}

// ---------------------------------------------------------------------------
// Collection
// ---------------------------------------------------------------------------

export async function fetchCollectionCards(): Promise<
  JsonApiResource<CollectionCardAttributes>[]
> {
  return fetchAll<CollectionCardAttributes>(
    '/node/collection_card?include=field_card' +
    '&fields[node--collection_card]=field_quantity_owned,field_quantity_foil,field_card' +
    '&fields[node--mtg_card]=title,field_mana_cost,field_cmc,field_type_line,field_colors,field_image_uri,field_price_usd',
  );
}

/**
 * Returns the estimated total USD value of all owned collection cards.
 *
 * Paginates through all collection_card nodes, fetching only quantity and
 * price, to avoid loading full card attributes for 108k records.
 */
export async function fetchCollectionValue(): Promise<number> {
  let total = 0;
  let next: string | null =
    '/node/collection_card?include=field_card' +
    '&fields[node--collection_card]=field_quantity_owned,field_card' +
    '&fields[node--mtg_card]=field_price_usd' +
    '&page[limit]=200';

  while (next !== null) {
    const page: {
      data: JsonApiResource<{ field_quantity_owned: number }>[];
      included?: JsonApiResource<{ field_price_usd: string | null }>[];
      links: { next?: { href: string } };
    } = (await client.get(next)).data;

    const priceByCardId = new Map<string, number>(
      (page.included ?? []).map((c: JsonApiResource<{ field_price_usd: string | null }>) => [
        c.id,
        parseFloat(c.attributes.field_price_usd ?? '0') || 0,
      ]),
    );

    for (const cc of page.data) {
      const ref = cc.relationships?.field_card?.data;
      if (ref == null || Array.isArray(ref)) continue;
      const price = priceByCardId.get(ref.id) ?? 0;
      const qty = cc.attributes.field_quantity_owned ?? 0;
      total += price * qty;
    }

    next = page.links.next?.href ?? null;
  }

  return Math.round(total * 100) / 100;
}

export async function upsertCollectionCard(
  cardId: string,
  cardName: string,
  quantityOwned: number,
  quantityFoil = 0,
  existingId?: string,
): Promise<JsonApiResource<CollectionCardAttributes>> {
  if (existingId !== undefined) {
    const response = await client.patch<
      JsonApiSingleResponse<CollectionCardAttributes>
    >(`/node/collection_card/${existingId}`, {
      data: {
        type: 'node--collection_card',
        id: existingId,
        attributes: {
          title: cardName,
          field_quantity_owned: quantityOwned,
          field_quantity_foil: quantityFoil,
        },
      },
    });
    return response.data.data;
  }

  const response = await client.post<
    JsonApiSingleResponse<CollectionCardAttributes>
  >('/node/collection_card', {
    data: {
      type: 'node--collection_card',
      attributes: {
        title: cardName,
        field_quantity_owned: quantityOwned,
        field_quantity_foil: quantityFoil,
        status: true,
      },
      relationships: {
        field_card: { data: { type: 'node--mtg_card', id: cardId } },
      },
    },
  });
  return response.data.data;
}

/**
 * Fetches the collection_card node for a specific mtg_card UUID, if owned.
 */
export async function fetchCollectionCardByCardId(
  cardId: string,
): Promise<JsonApiResource<CollectionCardAttributes> | null> {
  const response = await client.get<JsonApiCollectionResponse<CollectionCardAttributes>>(
    `/node/collection_card` +
    `?filter[field_card.id]=${cardId}` +
    `&fields[node--collection_card]=field_quantity_owned,field_quantity_foil,field_card` +
    `&page[limit]=1`,
  );
  return response.data.data[0] ?? null;
}
