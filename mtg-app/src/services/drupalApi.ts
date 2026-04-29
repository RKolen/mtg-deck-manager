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

/**
 * Searches cards by name using a JSON:API filter. Used during XLSX import
 * to match card names to existing Drupal nodes.
 */
export async function findCardsByName(
  name: string,
): Promise<JsonApiResource<MtgCardAttributes>[]> {
  const response = await client.get<JsonApiCollectionResponse<MtgCardAttributes>>(
    '/node--mtg_card',
    {
      params: {
        'filter[title]': name,
        'fields[node--mtg_card]':
          'title,field_mana_cost,field_cmc,field_type_line,field_colors,field_color_identity,field_oracle_text,field_scryfall_id,field_image_uri,field_is_mana_producer,field_produced_mana,field_legal_formats',
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
    '/node--deck?fields[node--deck]=title,field_format,field_notes',
  );
}

export async function fetchDeck(
  id: string,
): Promise<JsonApiResource<DeckAttributes>> {
  const response = await client.get<JsonApiSingleResponse<DeckAttributes>>(
    `/node--deck/${id}`,
  );
  return response.data.data;
}

export async function createDeck(
  attributes: Pick<DeckAttributes, 'title' | 'field_format' | 'field_notes'>,
): Promise<JsonApiResource<DeckAttributes>> {
  const response = await client.post<JsonApiSingleResponse<DeckAttributes>>(
    '/node--deck',
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
    `/node--deck/${id}`,
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
  await client.delete(`/node--deck/${id}`);
}

// ---------------------------------------------------------------------------
// Deck cards — direct reference model
//
// Decks reference mtg_card nodes directly via two multi-value fields:
//   field_main_cards    (cardinality 60) — each value = one copy of a card
//   field_sideboard_cards (cardinality 15)
//
// To have 4x Lightning Bolt: add the same card ID four times to the field.
// ---------------------------------------------------------------------------

const CARD_FIELDS =
  'title,field_mana_cost,field_cmc,field_type_line,' +
  'field_colors,field_color_identity,field_oracle_text,field_image_uri,' +
  'field_is_mana_producer,field_produced_mana,field_legal_formats';

/**
 * Fetches a deck with both card fields included and returns a flat list of
 * DeckCardWithCard slots (one per copy of each card).
 */
export async function fetchDeckCardsWithCards(
  deckId: string,
): Promise<DeckCardWithCard[]> {
  const response = await client.get<{
    data: JsonApiResource<DeckAttributes & {
      field_main_cards: JsonApiResourceIdentifier[];
      field_sideboard_cards: JsonApiResourceIdentifier[];
    }>;
    included?: JsonApiResource<MtgCardAttributes>[];
  }>(
    `/node--deck/${deckId}` +
    `?include=field_main_cards,field_sideboard_cards` +
    `&fields[node--mtg_card]=${CARD_FIELDS}`,
  );

  const cardMap = new Map<string, MtgCardAttributes & { id: string }>(
    (response.data.included ?? []).map(c => [c.id, { id: c.id, ...c.attributes }]),
  );

  const slots: DeckCardWithCard[] = [];

  // Build grouped slots: count occurrences of each card ID, then create one
  // DeckCardWithCard per unique card.
  function buildSlots(refs: JsonApiResourceIdentifier[], isSideboard: boolean): void {
    const counts = new Map<string, number>();
    for (const ref of refs) {
      counts.set(ref.id, (counts.get(ref.id) ?? 0) + 1);
    }
    for (const [cardId, quantity] of counts) {
      const card = cardMap.get(cardId);
      if (!card) continue;
      slots.push({ id: cardId, quantity, isSideboard, card });
    }
  }

  const rels = response.data.data.relationships ?? {};
  const mainRefs = (rels.field_main_cards?.data ?? []) as JsonApiResourceIdentifier[];
  const sbRefs = (rels.field_sideboard_cards?.data ?? []) as JsonApiResourceIdentifier[];

  buildSlots(mainRefs, false);
  buildSlots(sbRefs, true);

  return slots;
}

/**
 * Adds one copy of a card to a deck field by appending its ID to the
 * existing relationship list (POST relationship endpoint).
 */
export async function addCardToDeck(
  deckId: string,
  cardId: string,
  isSideboard = false,
): Promise<void> {
  const field = isSideboard ? 'field_sideboard_cards' : 'field_main_cards';
  await client.post(
    `/node--deck/${deckId}/relationships/${field}`,
    { data: [{ type: 'node--mtg_card', id: cardId }] },
  );
}

/**
 * Removes all copies of a card from a deck field and re-adds the desired
 * quantity. Used by +/- controls in the editor.
 *
 * JSON:API relationship PATCH replaces the entire list, so we must send the
 * full updated list every time.
 */
export async function setCardQuantityInDeck(
  deckId: string,
  cardId: string,
  quantity: number,
  isSideboard: boolean,
  allSlots: DeckCardWithCard[],
): Promise<void> {
  const field = isSideboard ? 'field_sideboard_cards' : 'field_main_cards';
  const sideboardFlag = isSideboard;

  // Build the complete new list for this field.
  const otherCards = allSlots.filter(s => s.isSideboard === sideboardFlag && s.card.id !== cardId);
  const retained: JsonApiResourceIdentifier[] = otherCards.flatMap(s =>
    Array.from({ length: s.quantity }, () => ({ type: 'node--mtg_card', id: s.card.id })),
  );
  const additions: JsonApiResourceIdentifier[] = quantity > 0
    ? Array.from({ length: quantity }, () => ({ type: 'node--mtg_card', id: cardId }))
    : [];

  await client.patch(
    `/node--deck/${deckId}/relationships/${field}`,
    { data: [...retained, ...additions] },
  );
}

/**
 * Removes all copies of a specific card from one field of the deck.
 */
export async function removeCardFromDeck(
  deckId: string,
  cardId: string,
  isSideboard: boolean,
  allSlots: DeckCardWithCard[],
): Promise<void> {
  return setCardQuantityInDeck(deckId, cardId, 0, isSideboard, allSlots);
}

// ---------------------------------------------------------------------------
// Collection
// ---------------------------------------------------------------------------

export async function fetchCollectionCards(): Promise<
  JsonApiResource<CollectionCardAttributes>[]
> {
  return fetchAll<CollectionCardAttributes>(
    '/node--collection_card?include=field_card&fields[node--collection_card]=field_quantity_owned,field_quantity_foil,field_card&fields[node--mtg_card]=title,field_mana_cost,field_cmc,field_type_line,field_colors,field_image_uri',
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
    >(`/node--collection_card/${existingId}`, {
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
  >('/node--collection_card', {
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
