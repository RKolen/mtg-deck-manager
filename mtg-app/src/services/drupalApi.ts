/**
 * Typed JSON:API client for the MTG Deck Manager Drupal backend.
 *
 * All mutations go through this module. Build-time card data is handled by
 * gatsby-source-drupal + GraphQL; this client handles everything dynamic:
 * decks, collection quantities, and deck-card relationships.
 */

import axios, { type AxiosInstance } from 'axios';
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

const DRUPAL_URL = process.env.GATSBY_DRUPAL_URL ?? 'https://mtg-deck-manager.ddev.site';

const client: AxiosInstance = axios.create({
  baseURL: `${DRUPAL_URL}/jsonapi`,
  headers: {
    'Content-Type': 'application/vnd.api+json',
    Accept: 'application/vnd.api+json',
  },
  // Single-user app — use Basic Auth for simplicity.
  // Credentials are read from env vars so they are not hard-coded.
  auth: {
    username: process.env.GATSBY_DRUPAL_USER ?? 'admin',
    password: process.env.GATSBY_DRUPAL_PASS ?? 'admin',
  },
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
  'title,field_mana_cost,field_cmc,field_type_line,field_colors,field_color_identity,field_oracle_text,field_image_uri,field_is_mana_producer,field_produced_mana,field_legal_formats';

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
    '/node/deck?fields[node--deck]=title,field_format,field_notes',
  );
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
// Deck cards — deck_card node model
//
// Each card slot is a `deck_card` node with:
//   field_card          entity reference → mtg_card
//   field_deck          entity reference → deck
//   field_quantity      integer (how many copies)
//   field_is_sideboard  boolean
//
// To fetch a deck's cards: filter deck_card nodes by field_deck.id.
// ---------------------------------------------------------------------------

const DECK_CARD_FIELDS =
  'title,field_mana_cost,field_cmc,field_type_line,' +
  'field_colors,field_color_identity,field_oracle_text,field_image_uri,' +
  'field_is_mana_producer,field_produced_mana,field_legal_formats';

interface DeckCardNodeAttributes {
  title: string;
  field_quantity: number;
  field_is_sideboard: boolean;
}

/**
 * Fetches all deck_card nodes for a deck, including the referenced mtg_card
 * nodes, and returns them as DeckCardWithCard slots.
 */
export async function fetchDeckCardsWithCards(
  deckId: string,
): Promise<DeckCardWithCard[]> {
  const response = await client.get<{
    data: JsonApiResource<DeckCardNodeAttributes>[];
    included?: JsonApiResource<MtgCardAttributes>[];
  }>(
    `/node/deck_card` +
    `?filter[field_deck.id]=${deckId}` +
    `&include=field_card` +
    `&fields[node--deck_card]=field_quantity,field_is_sideboard,field_card` +
    `&fields[node--mtg_card]=${DECK_CARD_FIELDS}` +
    `&page[limit]=200`,
  );

  const cardMap = new Map<string, MtgCardAttributes & { id: string }>(
    (response.data.included ?? []).map(c => [c.id, { id: c.id, ...c.attributes }]),
  );

  return response.data.data.flatMap(node => {
    const cardRef = (node.relationships?.field_card?.data) as JsonApiResourceIdentifier | null;
    if (!cardRef) return [];
    const card = cardMap.get(cardRef.id);
    if (!card) return [];
    return [{
      id: node.id,
      quantity: node.attributes.field_quantity ?? 1,
      isSideboard: node.attributes.field_is_sideboard ?? false,
      card,
    }];
  });
}

/**
 * Creates a deck_card node with a specific quantity in one call.
 * Used by the import page.
 */
export async function importCardToDeck(
  deckId: string,
  cardId: string,
  quantity: number,
  isSideboard: boolean,
  cardName: string,
): Promise<void> {
  await client.post<JsonApiSingleResponse<DeckCardNodeAttributes>>(
    '/node/deck_card',
    {
      data: {
        type: 'node--deck_card',
        attributes: {
          title: cardName,
          status: true,
          field_quantity: quantity,
          field_is_sideboard: isSideboard,
        },
        relationships: {
          field_card: { data: { type: 'node--mtg_card', id: cardId } },
          field_deck: { data: { type: 'node--deck', id: deckId } },
        },
      },
    },
  );
}

/**
 * Adds a card slot to a deck. If a deck_card node already exists for this
 * card in the same zone, increments its quantity instead.
 */
export async function addCardToDeck(
  deckId: string,
  cardId: string,
  isSideboard = false,
  existingSlots: DeckCardWithCard[] = [],
  cardName = 'Unknown card',
): Promise<void> {
  const existing = existingSlots.find(
    s => s.card.id === cardId && s.isSideboard === isSideboard,
  );

  if (existing != null) {
    await setCardQuantityInDeck(
      cardId, existing.quantity + 1, isSideboard, existingSlots,
    );
    return;
  }

  await importCardToDeck(deckId, cardId, 1, isSideboard, cardName);
}

/**
 * Updates the quantity on an existing deck_card node.
 * If quantity reaches 0, deletes the node instead.
 */
export async function setCardQuantityInDeck(
  cardId: string,
  quantity: number,
  isSideboard: boolean,
  allSlots: DeckCardWithCard[],
): Promise<void> {
  const slot = allSlots.find(
    s => s.card.id === cardId && s.isSideboard === isSideboard,
  );
  if (!slot) return;

  if (quantity <= 0) {
    await removeCardFromDeck(cardId, isSideboard, allSlots);
    return;
  }

  await client.patch(
    `/node/deck_card/${slot.id}`,
    {
      data: {
        type: 'node--deck_card',
        id: slot.id,
        attributes: { field_quantity: quantity },
      },
    },
  );
}

/**
 * Deletes a deck_card node entirely.
 */
export async function removeCardFromDeck(
  cardId: string,
  isSideboard: boolean,
  allSlots: DeckCardWithCard[],
): Promise<void> {
  const slot = allSlots.find(
    s => s.card.id === cardId && s.isSideboard === isSideboard,
  );
  if (!slot) return;

  await client.delete(`/node/deck_card/${slot.id}`);
}

// ---------------------------------------------------------------------------
// Collection
// ---------------------------------------------------------------------------

export async function fetchCollectionCards(): Promise<
  JsonApiResource<CollectionCardAttributes>[]
> {
  return fetchAll<CollectionCardAttributes>(
    '/node/collection_card?include=field_card&fields[node--collection_card]=field_quantity_owned,field_quantity_foil,field_card&fields[node--mtg_card]=title,field_mana_cost,field_cmc,field_type_line,field_colors,field_image_uri',
  );
}

export async function upsertCollectionCard(
  cardId: string,
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
        title: `collection_${cardId}`,
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
