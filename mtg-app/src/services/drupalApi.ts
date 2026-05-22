import { gql } from 'graphql-request';
import type {
  CollectionCardAttributes,
  DeckAttributes,
  DeckCardWithCard,
  JsonApiCollectionResponse,
  JsonApiResource,
  JsonApiSingleResponse,
  MtgCardAttributes,
} from '../types/drupal';
import { getGraphQLClient } from './graphqlClient';
import { slugify } from '../utils/slugify';

// ---------------------------------------------------------------------------
// GraphQL response types (internal — pages still receive JSON:API-shaped objects)
// ---------------------------------------------------------------------------

interface GqlMtgCard {
  id: string;
  title: string;
  manaCost: string | null;
  cmc: number | null;
  typeLine: string | null;
  colors: string[];
  colorIdentity: string[];
  oracleText: string | null;
  imageUri: string | null;
  isManaProducer: boolean;
  producedMana: string[];
  legalFormats: string[];
  priceUsd: string | null;
  priceUsdFoil: string | null;
  setCode: string | null;
  setName: string | null;
  rarity: string | null;
  collectorNumber: string | null;
  power: string | null;
  toughness: string | null;
  loyalty: string | null;
}

interface GqlText {
  value?: string | null;
  processed?: string | null;
}

/** GraphQL Compose NodeDeck (id = entity id, uuid = public id). */
interface GqlComposeDeck {
  id: string;
  uuid: string;
  title: string;
  format: string;
  notes?: GqlText | null;
}

/** Custom MTG schema Deck (mutations). */
interface GqlDeck {
  id: string;
  nid: number;
  title: string;
  format: string;
  notes: string | null;
}

interface GqlComposeCollectionCard {
  id: string;
  uuid: string;
  quantityOwned: number;
  quantityFoil: number;
  card?: { uuid: string } | null;
}

interface GqlDeckCard {
  id: string;
  quantity: number;
  isSideboard: boolean;
  card: GqlMtgCard;
}

interface GqlCollectionCard {
  id: string;
  quantityOwned: number;
  quantityFoil: number;
  card: GqlMtgCard | null;
}

// ---------------------------------------------------------------------------
// Adapters — map clean GraphQL shapes back to the JSON:API-shaped types that
// the page components depend on. Keeps all pages unchanged.
// ---------------------------------------------------------------------------

/** Maps a GraphQL MtgCard node to the resource shape used by pages. */
export function gqlCardToResource(c: GqlMtgCard): JsonApiResource<MtgCardAttributes> {
  return toCardResource(c);
}

function toCardResource(c: GqlMtgCard): JsonApiResource<MtgCardAttributes> {
  return {
    id: c.id,
    type: 'node--mtg_card',
    attributes: {
      title: c.title,
      field_mana_cost: c.manaCost ?? '',
      field_cmc: c.cmc ?? 0,
      field_type_line: c.typeLine ?? '',
      field_colors: c.colors,
      field_color_identity: c.colorIdentity,
      field_oracle_text: c.oracleText != null
        ? { value: c.oracleText, format: null, processed: c.oracleText }
        : null,
      field_scryfall_id: '',
      field_image_uri: c.imageUri ?? '',
      field_is_mana_producer: c.isManaProducer,
      field_produced_mana: c.producedMana,
      field_legal_formats: c.legalFormats,
      field_price_usd: c.priceUsd ?? null,
      field_price_usd_foil: c.priceUsdFoil ?? null,
      field_price_eur: null,
      field_set_code: c.setCode ?? '',
      field_set_name: c.setName ?? '',
      field_rarity: c.rarity ?? '',
      field_collector_number: c.collectorNumber ?? '',
      field_combo_pieces: [],
      field_power: c.power ?? null,
      field_toughness: c.toughness ?? null,
      field_loyalty: c.loyalty ?? null,
    },
  };
}

function composePlainText(text: GqlText | null | undefined): string | null {
  if (!text) {
    return null;
  }
  return text.value ?? text.processed ?? null;
}

function toDeckResourceFromCompose(d: GqlComposeDeck): JsonApiResource<DeckAttributes> {
  return {
    id: d.uuid,
    type: 'node--deck',
    attributes: {
      title: d.title,
      field_format: d.format,
      field_notes: composePlainText(d.notes),
      drupal_internal__nid: parseInt(d.id, 10),
    },
  };
}

function toDeckResource(d: GqlDeck): JsonApiResource<DeckAttributes> {
  return {
    id: d.id,
    type: 'node--deck',
    attributes: {
      title: d.title,
      field_format: d.format,
      field_notes: d.notes ?? null,
      drupal_internal__nid: d.nid,
    },
  };
}

function toCollectionCardFromCompose(
  cc: GqlComposeCollectionCard,
): JsonApiResource<CollectionCardAttributes> {
  return {
    id: cc.uuid,
    type: 'node--collection_card',
    attributes: {
      field_quantity_owned: cc.quantityOwned,
      field_quantity_foil: cc.quantityFoil,
    },
    relationships: {
      field_card: {
        data: cc.card != null ? { id: cc.card.uuid, type: 'node--mtg_card' } : null,
      },
    },
  };
}

function toDeckCardWithCard(d: GqlDeckCard): DeckCardWithCard {
  const c = d.card;
  return {
    id: d.id,
    quantity: d.quantity,
    isSideboard: d.isSideboard,
    card: {
      id: c.id,
      title: c.title,
      field_mana_cost: c.manaCost ?? '',
      field_cmc: c.cmc ?? 0,
      field_type_line: c.typeLine ?? '',
      field_colors: c.colors,
      field_color_identity: c.colorIdentity,
      // The deck page handles oracle_text as either string or {value} — pass as string.
      field_oracle_text: c.oracleText as unknown as MtgCardAttributes['field_oracle_text'],
      field_scryfall_id: '',
      field_image_uri: c.imageUri ?? '',
      field_is_mana_producer: c.isManaProducer,
      field_produced_mana: c.producedMana,
      field_legal_formats: c.legalFormats,
      field_price_usd: null,
      field_price_usd_foil: null,
      field_price_eur: null,
      field_set_code: '',
      field_set_name: '',
      field_rarity: '',
      field_collector_number: '',
      field_combo_pieces: [],
      field_power: null,
      field_toughness: null,
      field_loyalty: null,
    },
  };
}

function toCollectionCardResource(cc: GqlCollectionCard): JsonApiResource<CollectionCardAttributes> {
  return {
    id: cc.id,
    type: 'node--collection_card',
    attributes: {
      field_quantity_owned: cc.quantityOwned,
      field_quantity_foil: cc.quantityFoil,
    },
    relationships: {
      field_card: {
        data: cc.card != null ? { id: cc.card.id, type: 'node--mtg_card' } : null,
      },
    },
  };
}

// ---------------------------------------------------------------------------
// GraphQL fragments
// ---------------------------------------------------------------------------

const CARD_FIELDS = gql`
  fragment CardFields on MtgCard {
    id title manaCost cmc typeLine colors colorIdentity
    oracleText imageUri isManaProducer producedMana legalFormats
    priceUsd priceUsdFoil setCode setName rarity collectorNumber
  }
`;

const CARD_DETAIL_FIELDS = gql`
  fragment CardDetailFields on MtgCard {
    id title manaCost cmc typeLine colors colorIdentity
    oracleText imageUri isManaProducer producedMana legalFormats
    priceUsd priceUsdFoil setCode setName rarity collectorNumber
    power toughness loyalty
  }
`;

const COMPOSE_DECK_FIELDS = gql`
  fragment ComposeDeckFields on NodeDeck {
    id uuid title format notes { value processed }
  }
`;

const MTG_DECK_FIELDS = gql`
  fragment DeckFields on Deck {
    id nid title format notes
  }
`;

const COLLECTION_CARD_FIELDS = gql`
  fragment CollectionCardFields on CollectionCard {
    id quantityOwned quantityFoil
    card { id }
  }
`;

// ---------------------------------------------------------------------------
// MTG Card queries
// ---------------------------------------------------------------------------

export interface CardPage {
  cards: JsonApiResource<MtgCardAttributes>[];
  nextUrl: string | null;
}

export async function fetchCardsPage(
  pageUrl: string | null,
  filters: {
    name?: string;
    colors?: string[];
    type?: string;
    maxCmc?: number | null;
  } = {},
): Promise<CardPage> {
  // pageUrl encodes the page number as a plain integer string when set.
  const page = pageUrl != null ? parseInt(pageUrl, 10) : 0;

  const query = gql`
    ${CARD_FIELDS}
    query GetCards(
      $page: Int, $name: String, $colors: [String!],
      $type: String, $maxCmc: Float
    ) {
      cards(page: $page, limit: 50, name: $name, colors: $colors, type: $type, maxCmc: $maxCmc) {
        cards { ...CardFields }
        nextCursor
      }
    }
  `;

  const data = await getGraphQLClient().request<{
    cards: { cards: GqlMtgCard[]; nextCursor: string | null };
  }>(query, {
    page,
    name: filters.name || null,
    colors: filters.colors?.length ? filters.colors : null,
    type: filters.type !== 'All' ? (filters.type || null) : null,
    maxCmc: filters.maxCmc ?? null,
  });

  return {
    cards: data.cards.cards.map(toCardResource),
    nextUrl: data.cards.nextCursor,
  };
}

export async function fetchCardBySlug(
  slug: string,
): Promise<JsonApiResource<MtgCardAttributes> | null> {
  const query = gql`
    ${CARD_DETAIL_FIELDS}
    query GetCard($slug: String!) {
      card(slug: $slug) { ...CardDetailFields }
    }
  `;

  const data = await getGraphQLClient().request<{ card: GqlMtgCard | null }>(query, { slug });
  return data.card != null ? toCardResource(data.card) : null;
}

export async function findCardsByName(
  name: string,
): Promise<JsonApiResource<MtgCardAttributes>[]> {
  const query = gql`
    ${CARD_FIELDS}
    query FindCards($name: String!) {
      cardsByName(name: $name) { ...CardFields }
    }
  `;

  const data = await getGraphQLClient().request<{ cardsByName: GqlMtgCard[] }>(query, { name });
  return data.cardsByName.map(toCardResource);
}

// ---------------------------------------------------------------------------
// Deck queries and mutations
// ---------------------------------------------------------------------------

export async function fetchDecks(): Promise<JsonApiResource<DeckAttributes>[]> {
  const query = gql`
    ${COMPOSE_DECK_FIELDS}
    query GetDecks {
      nodeDecks(first: 100, sortKey: TITLE) {
        nodes { ...ComposeDeckFields }
      }
    }
  `;
  const data = await getGraphQLClient().request<{
    nodeDecks: { nodes: GqlComposeDeck[] };
  }>(query);
  return data.nodeDecks.nodes.map(toDeckResourceFromCompose);
}

export async function fetchDeckBySlug(
  slug: string,
): Promise<JsonApiResource<DeckAttributes> | null> {
  const decks = await fetchDecks();
  return decks.find(d => slugify(d.attributes.title) === slug) ?? null;
}

export async function fetchDeck(
  id: string,
): Promise<JsonApiResource<DeckAttributes>> {
  const query = gql`
    ${COMPOSE_DECK_FIELDS}
    query GetDeck($id: ID!) { nodeDeck(id: $id) { ...ComposeDeckFields } }
  `;
  const data = await getGraphQLClient().request<{ nodeDeck: GqlComposeDeck }>(query, { id });
  return toDeckResourceFromCompose(data.nodeDeck);
}

export async function createDeck(
  attributes: Pick<DeckAttributes, 'title' | 'field_format' | 'field_notes'>,
): Promise<JsonApiResource<DeckAttributes>> {
  const mutation = gql`
    ${MTG_DECK_FIELDS}
    mutation CreateDeck($title: String!, $format: String!, $notes: String) {
      createDeck(title: $title, format: $format, notes: $notes) { ...DeckFields }
    }
  `;
  const data = await getGraphQLClient().request<{ createDeck: GqlDeck }>(mutation, {
    title: attributes.title,
    format: attributes.field_format,
    notes: attributes.field_notes ?? null,
  });
  return toDeckResource(data.createDeck);
}

export async function updateDeck(
  id: string,
  attributes: Partial<DeckAttributes>,
): Promise<JsonApiResource<DeckAttributes>> {
  const mutation = gql`
    ${MTG_DECK_FIELDS}
    mutation UpdateDeck($id: ID!, $title: String, $format: String, $notes: String) {
      updateDeck(id: $id, title: $title, format: $format, notes: $notes) { ...DeckFields }
    }
  `;
  const data = await getGraphQLClient().request<{ updateDeck: GqlDeck }>(mutation, {
    id,
    title: attributes.title ?? null,
    format: attributes.field_format ?? null,
    notes: attributes.field_notes ?? null,
  });
  return toDeckResource(data.updateDeck);
}

export async function deleteDeck(id: string): Promise<void> {
  const mutation = gql`
    mutation DeleteDeck($id: ID!) { deleteDeck(id: $id) }
  `;
  await getGraphQLClient().request(mutation, { id });
}

// ---------------------------------------------------------------------------
// Deck cards (GraphQL Compose paragraphs + MTG extension mutations)
// ---------------------------------------------------------------------------

interface GqlComposeDeckCard {
  uuid: string;
  quantity: number;
  isSideboard: boolean;
  card: GqlMtgCard | null;
}

const COMPOSE_DECK_CARD_FIELDS = gql`
  fragment ComposeDeckCardFields on ParagraphDeckCard {
    uuid
    quantity
    isSideboard
    card {
      ... on NodeMtgCard {
        uuid
        title
        manaCost
        cmc
        typeLine
        colors
        colorIdentity
        oracleText
        imageUri
        isManaProducer
        producedMana
        legalFormats
      }
    }
  }
`;

function composeCardToGql(card: GqlMtgCard & { uuid?: string }): GqlMtgCard {
  return { ...card, id: card.uuid ?? card.id };
}

function toDeckCardFromCompose(slot: GqlComposeDeckCard): DeckCardWithCard {
  if (slot.card == null) {
    throw new Error('Deck card paragraph is missing its card reference');
  }
  const mapped = toDeckCardWithCard({
    id: slot.uuid,
    quantity: slot.quantity,
    isSideboard: slot.isSideboard,
    card: composeCardToGql(slot.card),
  });
  return mapped;
}

export async function fetchDeckCardsWithCards(
  deckId: string,
): Promise<DeckCardWithCard[]> {
  const query = gql`
    ${COMPOSE_DECK_CARD_FIELDS}
    query GetDeckWithCards($id: ID!) {
      nodeDeck(id: $id) {
        deckCards {
          ...ComposeDeckCardFields
        }
      }
    }
  `;
  const data = await getGraphQLClient().request<{
    nodeDeck: { deckCards: GqlComposeDeckCard[] } | null;
  }>(query, { id: deckId });
  const slots = data.nodeDeck?.deckCards ?? [];
  return slots.filter(s => s.card != null).map(toDeckCardFromCompose);
}

async function deckCardAdd(
  deckId: string,
  cardId: string,
  quantity: number,
  isSideboard: boolean,
): Promise<void> {
  const mutation = gql`
    mutation DeckCardAdd(
      $deckId: ID!, $cardId: ID!, $quantity: Int!, $isSideboard: Boolean!
    ) {
      deckCardAdd(
        deckId: $deckId, cardId: $cardId, quantity: $quantity, isSideboard: $isSideboard
      ) { id }
    }
  `;
  await getGraphQLClient().request(mutation, { deckId, cardId, quantity, isSideboard });
}

async function deckCardUpdate(
  deckId: string,
  slotId: string,
  quantity: number,
): Promise<void> {
  const mutation = gql`
    mutation DeckCardUpdate($deckId: ID!, $slotId: ID!, $quantity: Int!) {
      deckCardUpdate(deckId: $deckId, slotId: $slotId, quantity: $quantity) { id }
    }
  `;
  await getGraphQLClient().request(mutation, { deckId, slotId, quantity });
}

async function deckCardRemove(deckId: string, slotId: string): Promise<void> {
  const mutation = gql`
    mutation DeckCardRemove($deckId: ID!, $slotId: ID!) {
      deckCardRemove(deckId: $deckId, slotId: $slotId)
    }
  `;
  await getGraphQLClient().request(mutation, { deckId, slotId });
}

export async function importCardToDeck(
  deckId: string,
  cards: { cardId: string; quantity: number; isSideboard: boolean; cardName: string }[],
): Promise<void> {
  for (const c of cards) {
    await deckCardAdd(deckId, c.cardId, c.quantity, c.isSideboard);
  }
}

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

  await deckCardAdd(deckId, cardId, 1, isSideboard);
}

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
  await deckCardUpdate(deckId, slotId, quantity);
}

export async function removeCardFromDeck(
  slotId: string,
  deckId: string,
  _allSlots: DeckCardWithCard[],
): Promise<void> {
  await deckCardRemove(deckId, slotId);
}

// ---------------------------------------------------------------------------
// Collection queries and mutations
// ---------------------------------------------------------------------------

export async function fetchCollectionCards(): Promise<
  JsonApiResource<CollectionCardAttributes>[]
> {
  const query = gql`
    query GetCollectionCards {
      nodeCollectionCards(first: 500) {
        nodes {
          id uuid quantityOwned quantityFoil
          card { uuid }
        }
      }
    }
  `;
  const data = await getGraphQLClient().request<{
    nodeCollectionCards: { nodes: GqlComposeCollectionCard[] };
  }>(query);
  return data.nodeCollectionCards.nodes.map(toCollectionCardFromCompose);
}

export async function fetchCollectionValue(): Promise<number> {
  const query = gql`
    query GetCollectionValue { collectionValue }
  `;
  const data = await getGraphQLClient().request<{ collectionValue: number }>(query);
  return data.collectionValue;
}

export async function upsertCollectionCard(
  cardId: string,
  cardName: string,
  quantityOwned: number,
  quantityFoil = 0,
  existingId?: string,
): Promise<JsonApiResource<CollectionCardAttributes>> {
  const mutation = gql`
    mutation UpsertCollection(
      $cardId: ID!, $cardName: String!,
      $quantityOwned: Int!, $quantityFoil: Int, $existingId: ID
    ) {
      upsertCollectionCard(
        cardId: $cardId, cardName: $cardName,
        quantityOwned: $quantityOwned, quantityFoil: $quantityFoil,
        existingId: $existingId
      ) {
        id quantityOwned quantityFoil
        card { id }
      }
    }
  `;
  const data = await getGraphQLClient().request<{ upsertCollectionCard: GqlCollectionCard }>(
    mutation,
    { cardId, cardName, quantityOwned, quantityFoil, existingId: existingId ?? null },
  );
  return toCollectionCardResource(data.upsertCollectionCard);
}

export async function fetchCollectionCardByCardId(
  cardId: string,
): Promise<JsonApiResource<CollectionCardAttributes> | null> {
  const query = gql`
    query GetCollectionCardByCard($cardId: ID!) {
      collectionCardByCardId(cardId: $cardId) {
        id quantityOwned quantityFoil
        card { id }
      }
    }
  `;
  const data = await getGraphQLClient().request<{
    collectionCardByCardId: GqlCollectionCard | null;
  }>(query, { cardId });
  return data.collectionCardByCardId != null
    ? toCollectionCardResource(data.collectionCardByCardId)
    : null;
}

// Re-export JSON:API types that are still used by other services / pages.
// These are kept in types/drupal.ts — nothing to re-export here, but the
// import above ensures the types are available for callers that do:
//   import type { ... } from '../services/drupalApi'
export type { JsonApiResource, JsonApiCollectionResponse, JsonApiSingleResponse };
