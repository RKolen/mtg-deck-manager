import { gql } from 'graphql-request';
import type {
  CardUse,
  CollectionCardAttributes,
  CollectionImportResult,
  CollectionImportRow,
  DeckAttributes,
  DeckBoard,
  DeckCardWithCard,
  DeckCommander,
  JsonApiCollectionResponse,
  JsonApiResource,
  JsonApiSingleResponse,
  MtgCardAttributes,
  PoolCard,
  PoolSource,
  WishIntent,
  WishlistItem,
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
  restrictedFormats: string[];
  priceUsd: string | null;
  priceUsdFoil: string | null;
  priceEur: string | null;
  priceEurFoil: string | null;
  setCode: string | null;
  setName: string | null;
  rarity: string | null;
  collectorNumber: string | null;
  power: string | null;
  toughness: string | null;
  loyalty: string | null;
  fullArt?: boolean | null;
  borderColor?: string | null;
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
  isFoil?: boolean | null;
  notes?: GqlText | null;
  changed?: { timestamp: number } | null;
  commander?: GqlMtgCard | null;
  commanderIsFoil?: boolean | null;
}

/** Custom MTG schema Deck (mutations). */
interface GqlDeck {
  id: string;
  nid: number;
  title: string;
  format: string;
  notes: string | null;
  commander?: GqlMtgCard | null;
  commanderIsFoil?: boolean | null;
}

interface GqlDeckCard {
  id: string;
  quantity: number;
  isSideboard: boolean;
  isFoil?: boolean | null;
  board?: DeckBoard | null;
  card: GqlMtgCard;
}

interface GqlCollectionCard {
  id: string;
  quantityOwned: number;
  quantityFoil: number;
  quantityTrade?: number | null;
  binderLocation?: string | null;
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
      field_restricted_formats: c.restrictedFormats ?? [],
      field_price_usd: c.priceUsd ?? null,
      field_price_usd_foil: c.priceUsdFoil ?? null,
      field_price_eur: c.priceEur ?? null,
      field_price_eur_foil: c.priceEurFoil ?? null,
      field_set_code: c.setCode ?? '',
      field_set_name: c.setName ?? '',
      field_rarity: c.rarity ?? '',
      field_collector_number: c.collectorNumber ?? '',
      field_combo_pieces: [],
      field_power: c.power ?? null,
      field_toughness: c.toughness ?? null,
      field_loyalty: c.loyalty ?? null,
      field_full_art: Boolean(c.fullArt),
      field_border_color: c.borderColor ?? '',
    },
  };
}

function composePlainText(text: GqlText | null | undefined): string | null {
  if (!text) {
    return null;
  }
  return text.value ?? text.processed ?? null;
}

function toDeckCommander(c: GqlMtgCard | null | undefined): DeckCommander | null {
  if (c == null) {
    return null;
  }
  return {
    id: c.id,
    title: c.title,
    field_type_line: c.typeLine ?? '',
    field_mana_cost: c.manaCost ?? '',
    field_cmc: c.cmc ?? 0,
    field_color_identity: c.colorIdentity ?? [],
    field_oracle_text: c.oracleText ?? '',
    field_image_uri: c.imageUri ?? '',
    field_legal_formats: c.legalFormats ?? [],
    field_restricted_formats: c.restrictedFormats ?? [],
    field_set_code: c.setCode ?? '',
    field_set_name: c.setName ?? '',
    field_collector_number: c.collectorNumber ?? '',
    field_price_usd: c.priceUsd ?? null,
    field_price_eur: c.priceEur ?? null,
    field_price_usd_foil: c.priceUsdFoil ?? null,
    field_price_eur_foil: c.priceEurFoil ?? null,
  };
}

function toDeckResourceFromCompose(d: GqlComposeDeck): JsonApiResource<DeckAttributes> {
  return {
    id: d.uuid,
    type: 'node--deck',
    attributes: {
      title: d.title,
      field_format: d.format,
      field_notes: composePlainText(d.notes),
      field_is_foil: Boolean(d.isFoil),
      drupal_internal__nid: parseInt(d.id, 10),
      changed: d.changed?.timestamp ?? null,
      field_commander: toDeckCommander(d.commander),
      field_commander_foil: Boolean(d.commanderIsFoil),
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
      field_commander: toDeckCommander(d.commander),
      field_commander_foil: Boolean(d.commanderIsFoil),
    },
  };
}

function toDeckCardWithCard(d: GqlDeckCard): DeckCardWithCard {
  const c = d.card;
  return {
    id: d.id,
    quantity: d.quantity,
    isSideboard: d.isSideboard,
    isFoil: Boolean(d.isFoil),
    board: d.board ?? (d.isSideboard ? 'side' : 'main'),
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
      field_restricted_formats: c.restrictedFormats ?? [],
      field_price_usd: c.priceUsd ?? null,
      field_price_usd_foil: c.priceUsdFoil ?? null,
      field_price_eur: c.priceEur ?? null,
      field_price_eur_foil: c.priceEurFoil ?? null,
      field_set_code: c.setCode ?? '',
      field_set_name: c.setName ?? '',
      field_rarity: c.rarity ?? '',
      field_collector_number: c.collectorNumber ?? '',
      field_combo_pieces: [],
      field_power: c.power ?? null,
      field_toughness: c.toughness ?? null,
      field_loyalty: c.loyalty ?? null,
      field_full_art: Boolean(c.fullArt),
      field_border_color: c.borderColor ?? '',
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
      field_quantity_trade: cc.quantityTrade ?? 0,
      field_binder_location: cc.binderLocation ?? null,
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
    oracleText imageUri isManaProducer producedMana legalFormats restrictedFormats
    priceUsd priceUsdFoil priceEur priceEurFoil setCode setName rarity collectorNumber
    fullArt borderColor
  }
`;

const CARD_DETAIL_FIELDS = gql`
  fragment CardDetailFields on MtgCard {
    id title manaCost cmc typeLine colors colorIdentity
    oracleText imageUri isManaProducer producedMana legalFormats restrictedFormats
    priceUsd priceUsdFoil priceEur priceEurFoil setCode setName rarity collectorNumber
    power toughness loyalty
    fullArt borderColor
  }
`;

const COMPOSE_DECK_FIELDS = gql`
  ${CARD_FIELDS}
  fragment ComposeDeckFields on NodeDeck {
    id uuid title format isFoil notes { value processed }
    changed { timestamp }
    commander { ...CardFields }
    commanderIsFoil
  }
`;

const MTG_DECK_FIELDS = gql`
  ${CARD_FIELDS}
  fragment DeckFields on Deck {
    id nid title format notes
    commander { ...CardFields }
    commanderIsFoil
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
    /** true lists only tokens and emblems; otherwise they are hidden. */
    tokens?: boolean;
  } = {},
): Promise<CardPage> {
  // pageUrl encodes the page number as a plain integer string when set.
  const page = pageUrl != null ? parseInt(pageUrl, 10) : 0;

  const query = gql`
    ${CARD_FIELDS}
    query GetCards(
      $page: Int, $name: String, $colors: [String!],
      $type: String, $maxCmc: Float, $tokens: Boolean
    ) {
      cards(
        page: $page, limit: 50, name: $name, colors: $colors, type: $type, maxCmc: $maxCmc,
        tokens: $tokens
      ) {
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
    tokens: filters.tokens === true ? true : null,
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
  options: { contains?: boolean; set?: string } = {},
): Promise<JsonApiResource<MtgCardAttributes>[]> {
  const query = gql`
    ${CARD_FIELDS}
    query FindCards($name: String!, $contains: Boolean, $set: String) {
      cardsByName(name: $name, contains: $contains, set: $set) { ...CardFields }
    }
  `;

  const data = await getGraphQLClient().request<{ cardsByName: GqlMtgCard[] }>(query, {
    name,
    contains: options.contains ?? false,
    set: options.set != null && options.set.trim() !== '' ? options.set.trim() : null,
  });
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

export async function fetchFormats(): Promise<{ name: string; slug: string }[]> {
  const query = gql`
    query GetFormats {
      formats { name slug }
    }
  `;
  const data = await getGraphQLClient().request<{
    formats: { name: string; slug: string }[];
  }>(query);
  return [...data.formats].sort((a, b) => a.name.localeCompare(b.name));
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
  attributes: Pick<DeckAttributes, 'title' | 'field_format' | 'field_notes'> & {
    commanderId?: string | null;
  },
): Promise<JsonApiResource<DeckAttributes>> {
  const mutation = gql`
    ${MTG_DECK_FIELDS}
    mutation CreateDeck($title: String!, $format: String!, $notes: String, $commanderId: ID) {
      createDeck(title: $title, format: $format, notes: $notes, commanderId: $commanderId) { ...DeckFields }
    }
  `;
  const data = await getGraphQLClient().request<{ createDeck: GqlDeck }>(mutation, {
    title: attributes.title,
    format: attributes.field_format,
    notes: attributes.field_notes ?? null,
    commanderId: attributes.commanderId ?? null,
  });
  return toDeckResource(data.createDeck);
}

export async function updateDeck(
  id: string,
  attributes: Partial<DeckAttributes> & {
    commanderId?: string | null;
    commanderFoil?: boolean;
  },
): Promise<JsonApiResource<DeckAttributes>> {
  const mutation = gql`
    ${MTG_DECK_FIELDS}
    mutation UpdateDeck(
      $id: ID!
      $title: String
      $format: String
      $notes: String
      $commanderId: ID
      $commanderFoil: Boolean
    ) {
      updateDeck(
        id: $id
        title: $title
        format: $format
        notes: $notes
        commanderId: $commanderId
        commanderFoil: $commanderFoil
      ) { ...DeckFields }
    }
  `;
  const variables: {
    id: string;
    title: string | null;
    format: string | null;
    notes: string | null;
    commanderId?: string;
    commanderFoil?: boolean;
  } = {
    id,
    title: attributes.title ?? null,
    format: attributes.field_format ?? null,
    notes: attributes.field_notes ?? null,
  };
  if ('commanderId' in attributes) {
    variables.commanderId = attributes.commanderId ?? '';
  }
  if ('commanderFoil' in attributes) {
    variables.commanderFoil = Boolean(attributes.commanderFoil);
  }
  const data = await getGraphQLClient().request<{ updateDeck: GqlDeck }>(mutation, variables);
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

/** GraphQL Compose NodeMtgCard (oracleText is a Text object, not a scalar). */
interface GqlComposeMtgCard {
  uuid: string;
  title: string;
  manaCost: string | null;
  cmc: number | null;
  typeLine: string | null;
  colors: string[];
  colorIdentity: string[];
  oracleText?: GqlText | null;
  imageUri: string | null;
  isManaProducer: boolean;
  producedMana: string[];
  legalFormats: string[];
  restrictedFormats?: string[] | null;
  priceUsd?: string | null;
  priceUsdFoil?: string | null;
  priceEur?: string | null;
  priceEurFoil?: string | null;
  setCode?: string | null;
  setName?: string | null;
  rarity?: string | null;
  collectorNumber?: string | null;
  power?: string | null;
  toughness?: string | null;
  loyalty?: string | null;
  fullArt?: boolean | null;
  borderColor?: string | null;
}

interface GqlComposeDeckCard {
  uuid: string;
  quantity: number;
  isSideboard: boolean;
  isFoil?: boolean | null;
  card: GqlComposeMtgCard | null;
}

const COMPOSE_DECK_CARD_FIELDS = gql`
  fragment ComposeDeckCardFields on ParagraphDeckCard {
    uuid
    quantity
    isSideboard
    isFoil
    card {
      ... on NodeMtgCard {
        uuid
        title
        manaCost
        cmc
        typeLine
        colors
        colorIdentity
        oracleText { value processed }
        imageUri
        isManaProducer
        producedMana
        legalFormats
        restrictedFormats
        priceUsd
        priceUsdFoil
        priceEur
        priceEurFoil
        setCode
        setName
        rarity
        collectorNumber
        power
        toughness
        loyalty
        fullArt
        borderColor
      }
    }
  }
`;

function composeMtgCardToGql(card: GqlComposeMtgCard): GqlMtgCard {
  return {
    id: card.uuid,
    title: card.title,
    manaCost: card.manaCost,
    cmc: card.cmc,
    typeLine: card.typeLine,
    colors: card.colors,
    colorIdentity: card.colorIdentity,
    oracleText: composePlainText(card.oracleText),
    imageUri: card.imageUri,
    isManaProducer: card.isManaProducer,
    producedMana: card.producedMana,
    legalFormats: card.legalFormats,
    restrictedFormats: card.restrictedFormats ?? [],
    priceUsd: card.priceUsd ?? null,
    priceUsdFoil: card.priceUsdFoil ?? null,
    priceEur: card.priceEur ?? null,
    priceEurFoil: card.priceEurFoil ?? null,
    setCode: card.setCode ?? null,
    setName: card.setName ?? null,
    rarity: card.rarity ?? null,
    collectorNumber: card.collectorNumber ?? null,
    power: card.power ?? null,
    toughness: card.toughness ?? null,
    loyalty: card.loyalty ?? null,
    fullArt: card.fullArt ?? null,
    borderColor: card.borderColor ?? null,
  };
}

function toDeckCardFromCompose(slot: GqlComposeDeckCard, maybe = false): DeckCardWithCard {
  if (slot.card == null) {
    throw new Error('Deck card paragraph is missing its card reference');
  }
  const mapped = toDeckCardWithCard({
    id: slot.uuid,
    quantity: slot.quantity,
    isSideboard: slot.isSideboard,
    isFoil: Boolean(slot.isFoil),
    board: maybe ? 'maybe' : (slot.isSideboard ? 'side' : 'main'),
    card: composeMtgCardToGql(slot.card),
  });
  return mapped;
}

async function fetchDeckSlots(deckId: string, field: 'deckCards' | 'maybeCards'): Promise<DeckCardWithCard[]> {
  const query = gql`
    ${COMPOSE_DECK_CARD_FIELDS}
    query GetDeckSlots($id: ID!) {
      nodeDeck(id: $id) {
        ${field} {
          ... on ParagraphDeckCard {
            ...ComposeDeckCardFields
          }
        }
      }
    }
  `;
  const data = await getGraphQLClient().request<{
    nodeDeck: Record<string, (GqlComposeDeckCard | null)[] | null> | null;
  }>(query, { id: deckId });
  return (data.nodeDeck?.[field] ?? [])
    .filter((s): s is GqlComposeDeckCard => s != null && s.card != null)
    .map(s => toDeckCardFromCompose(s, field === 'maybeCards'));
}

/** Main deck and sideboard slots. The maybeboard is loaded separately. */
export async function fetchDeckCardsWithCards(
  deckId: string,
): Promise<DeckCardWithCard[]> {
  return fetchDeckSlots(deckId, 'deckCards');
}

/**
 * Maybeboard slots (board 'maybe'). They never count toward deck size,
 * legality, value or simulation, so only the deck page loads them.
 */
export async function fetchDeckMaybeCards(deckId: string): Promise<DeckCardWithCard[]> {
  return fetchDeckSlots(deckId, 'maybeCards');
}

async function deckCardAdd(
  deckId: string,
  cardId: string,
  quantity: number,
  isSideboard: boolean,
  foil?: boolean,
  board?: DeckBoard,
): Promise<void> {
  const mutation = gql`
    mutation DeckCardAdd(
      $deckId: ID!, $cardId: ID!, $quantity: Int!, $isSideboard: Boolean!, $foil: Boolean,
      $board: String
    ) {
      deckCardAdd(
        deckId: $deckId, cardId: $cardId, quantity: $quantity,
        isSideboard: $isSideboard, foil: $foil, board: $board
      ) { id }
    }
  `;
  await getGraphQLClient().request(mutation, {
    deckId,
    cardId,
    quantity,
    isSideboard,
    foil: foil ?? null,
    board: board ?? null,
  });
}

/** Moves a slot to main, side or maybe; merges with the same printing there. */
export async function moveDeckCard(deckId: string, slotId: string, board: DeckBoard): Promise<void> {
  const mutation = gql`
    mutation DeckCardMove($deckId: ID!, $slotId: ID!, $board: String!) {
      deckCardMove(deckId: $deckId, slotId: $slotId, board: $board) { id }
    }
  `;
  await getGraphQLClient().request(mutation, { deckId, slotId, board });
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

export async function setDeckCardFoil(
  deckId: string,
  slotId: string,
  foil: boolean,
): Promise<void> {
  const mutation = gql`
    mutation DeckCardSetFoil($deckId: ID!, $slotId: ID!, $foil: Boolean!) {
      deckCardSetFoil(deckId: $deckId, slotId: $slotId, foil: $foil) { id }
    }
  `;
  await getGraphQLClient().request(mutation, { deckId, slotId, foil });
}

export async function replaceCommanderPrinting(
  deckId: string,
  nextCardId: string,
  nextCardName: string,
  collectionMode: 'none' | 'replace' | 'add',
  foil: boolean,
  previousCardId?: string,
  previousCardName?: string,
): Promise<void> {
  await updateDeck(deckId, { commanderId: nextCardId, commanderFoil: foil });
  if (collectionMode === 'none') {
    return;
  }

  const nextRow = await fetchCollectionCardByCardId(nextCardId);
  let nextOwned = nextRow?.attributes.field_quantity_owned ?? 0;
  let nextFoil = nextRow?.attributes.field_quantity_foil ?? 0;
  if (foil) {
    nextFoil += 1;
  } else {
    nextOwned += 1;
  }
  await upsertCollectionCard(
    nextCardId,
    nextCardName,
    nextOwned,
    nextFoil,
    nextRow?.id,
  );

  if (
    collectionMode === 'replace'
    && previousCardId != null
    && previousCardId !== nextCardId
  ) {
    const prevRow = await fetchCollectionCardByCardId(previousCardId);
    if (prevRow != null) {
      let prevOwned = prevRow.attributes.field_quantity_owned ?? 0;
      let prevFoilQty = prevRow.attributes.field_quantity_foil ?? 0;
      if (foil) {
        prevFoilQty = Math.max(0, prevFoilQty - 1);
      } else {
        prevOwned = Math.max(0, prevOwned - 1);
      }
      await upsertCollectionCard(
        previousCardId,
        previousCardName ?? nextCardName,
        prevOwned,
        prevFoilQty,
        prevRow.id,
      );
    }
  }
}

export async function replaceDeckCardPrinting(
  deckId: string,
  slotId: string,
  cardId: string,
  collectionMode: 'none' | 'replace' | 'add',
  foil: boolean,
): Promise<void> {
  const mutation = gql`
    mutation DeckCardReplacePrinting(
      $deckId: ID!, $slotId: ID!, $cardId: ID!,
      $collectionMode: String!, $foil: Boolean
    ) {
      deckCardReplacePrinting(
        deckId: $deckId, slotId: $slotId, cardId: $cardId,
        collectionMode: $collectionMode, foil: $foil
      ) { id }
    }
  `;
  await getGraphQLClient().request(mutation, {
    deckId,
    slotId,
    cardId,
    collectionMode,
    foil,
  });
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
  cards: {
    cardId: string;
    quantity: number;
    isSideboard: boolean;
    cardName: string;
    isFoil?: boolean;
  }[],
): Promise<void> {
  for (const c of cards) {
    await deckCardAdd(deckId, c.cardId, c.quantity, c.isSideboard, c.isFoil);
  }
}

export async function addCardToDeck(
  deckId: string,
  cardId: string,
  isSideboard = false,
  existingSlots: DeckCardWithCard[] = [],
  _cardName = '',
  foil?: boolean,
  board?: DeckBoard,
): Promise<void> {
  const target: DeckBoard = board ?? (isSideboard ? 'side' : 'main');
  // Foil and non-foil copies of a printing live in separate slots. Without
  // an explicit finish the server uses the deck default, which callers pass
  // in when they know it.
  const existing = existingSlots.find(
    s => s.card.id === cardId && s.board === target && (foil == null || s.isFoil === foil),
  );

  if (existing != null) {
    await setCardQuantityInDeck(existing.id, existing.quantity + 1, deckId, existingSlots);
    return;
  }

  await deckCardAdd(deckId, cardId, 1, target === 'side', foil, target);
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

/** Puts a removed slot back: same printing, quantity, finish and board. */
export async function restoreDeckSlot(deckId: string, slot: DeckCardWithCard): Promise<void> {
  await deckCardAdd(deckId, slot.card.id, slot.quantity, slot.board === 'side', slot.isFoil, slot.board);
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

interface GqlCollectionRow {
  id: string;
  cardId: string;
  title: string;
  quantityOwned: number;
  quantityFoil: number;
  quantityTrade: number;
  binderLocation: string | null;
  setCode: string | null;
  setName: string | null;
  collectorNumber: string | null;
  typeLine: string | null;
  cmc: number | null;
  priceUsd: string | null;
  priceUsdFoil: string | null;
  priceEur: string | null;
  priceEurFoil: string | null;
  imageUri: string | null;
  fullArt: boolean;
  borderColor: string | null;
}

/**
 * The whole collection in one request (one SQL query on the server).
 *
 * After a single add or edit, pages patch the changed row in the cache
 * (patchCollectionRow) instead of loading this list again.
 */
export async function fetchCollectionCards(): Promise<
  JsonApiResource<CollectionCardAttributes>[]
> {
  const query = gql`
    query GetCollectionRows {
      collectionRows {
        id cardId title quantityOwned quantityFoil quantityTrade binderLocation
        setCode setName collectorNumber typeLine cmc
        priceUsd priceUsdFoil priceEur priceEurFoil imageUri fullArt borderColor
      }
    }
  `;
  const data = await getGraphQLClient().request<{ collectionRows: GqlCollectionRow[] }>(query);
  return data.collectionRows.map(r => ({
    id: r.id,
    type: 'node--collection_card',
    attributes: {
      field_quantity_owned: r.quantityOwned,
      field_quantity_foil: r.quantityFoil,
      field_quantity_trade: r.quantityTrade,
      field_binder_location: r.binderLocation,
      field_card_title: r.title,
      field_set_code: r.setCode ?? '',
      field_set_name: r.setName ?? '',
      field_collector_number: r.collectorNumber ?? '',
      field_type_line: r.typeLine ?? '',
      field_cmc: r.cmc ?? 0,
      field_price_usd: r.priceUsd,
      field_price_eur: r.priceEur,
      field_price_eur_foil: r.priceEurFoil,
      field_price_usd_foil: r.priceUsdFoil,
      field_image_uri: r.imageUri,
      field_full_art: r.fullArt,
      field_border_color: r.borderColor ?? '',
    },
    relationships: {
      field_card: { data: { id: r.cardId, type: 'node--mtg_card' } },
    },
  }));
}

export function collectionPrintingId(
  cc: JsonApiResource<CollectionCardAttributes>,
): string | null {
  const rel = cc.relationships?.field_card?.data;
  const id = Array.isArray(rel) ? rel[0]?.id : rel?.id;
  return id ?? null;
}

export function collectionOwnedQty(
  cc: JsonApiResource<CollectionCardAttributes>,
): number {
  return (cc.attributes.field_quantity_owned ?? 0) + (cc.attributes.field_quantity_foil ?? 0);
}

export async function fetchCollectionValue(currency: 'USD' | 'EUR' = 'EUR'): Promise<number> {
  const query = gql`
    query GetCollectionValue($currency: String) {
      collectionValue(currency: $currency)
    }
  `;
  const data = await getGraphQLClient().request<{ collectionValue: number }>(query, {
    currency,
  });
  return data.collectionValue;
}

/** Euros per US dollar, for valuing cards that only have a USD price. */
export async function fetchUsdToEurRate(): Promise<number> {
  const query = gql`
    query GetUsdToEurRate {
      usdToEurRate
    }
  `;
  const data = await getGraphQLClient().request<{ usdToEurRate: number }>(query);
  return data.usdToEurRate;
}

export async function upsertCollectionCard(
  cardId: string,
  cardName: string,
  quantityOwned: number,
  quantityFoil = 0,
  existingId?: string,
  trade?: { quantityTrade?: number; binderLocation?: string },
): Promise<JsonApiResource<CollectionCardAttributes>> {
  const mutation = gql`
    mutation UpsertCollection(
      $cardId: ID!, $cardName: String!,
      $quantityOwned: Int!, $quantityFoil: Int, $existingId: ID,
      $quantityTrade: Int, $binderLocation: String
    ) {
      upsertCollectionCard(
        cardId: $cardId, cardName: $cardName,
        quantityOwned: $quantityOwned, quantityFoil: $quantityFoil,
        existingId: $existingId,
        quantityTrade: $quantityTrade, binderLocation: $binderLocation
      ) {
        id quantityOwned quantityFoil quantityTrade binderLocation
        card { id }
      }
    }
  `;
  const data = await getGraphQLClient().request<{ upsertCollectionCard: GqlCollectionCard }>(
    mutation,
    {
      cardId,
      cardName,
      quantityOwned,
      quantityFoil,
      existingId: existingId ?? null,
      quantityTrade: trade?.quantityTrade ?? null,
      binderLocation: trade?.binderLocation ?? null,
    },
  );
  return toCollectionCardResource(data.upsertCollectionCard);
}

export async function fetchCollectionCardByCardId(
  cardId: string,
): Promise<JsonApiResource<CollectionCardAttributes> | null> {
  const query = gql`
    query GetCollectionCardByCard($cardId: ID!) {
      collectionCardByCardId(cardId: $cardId) {
        id quantityOwned quantityFoil quantityTrade binderLocation
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

// ---------------------------------------------------------------------------
// Wishlist
// ---------------------------------------------------------------------------

const WISHLIST_FIELDS = gql`
  ${CARD_FIELDS}
  fragment WishlistFields on WishlistItem {
    id quantity anyPrinting foil minCondition notes owned done priceEur priceUsd
    card { ...CardFields }
    deck { id title }
    intent { id name }
  }
`;

interface GqlWishlistItem extends Omit<WishlistItem, 'card'> {
  card: GqlMtgCard | null;
}

function toWishlistItem(w: GqlWishlistItem): WishlistItem {
  return {
    ...w,
    card: w.card != null ? { id: w.card.id, ...toCardResource(w.card).attributes } : null,
  };
}

/** Wishes, optionally for one deck or intent. Done wishes only when asked. */
export async function fetchWishlist(
  filters: { deckId?: string | null; intentId?: string | null; includeDone?: boolean } = {},
): Promise<WishlistItem[]> {
  const query = gql`
    ${WISHLIST_FIELDS}
    query GetWishlist($deckId: ID, $intentId: ID, $includeDone: Boolean) {
      wishlist(deckId: $deckId, intentId: $intentId, includeDone: $includeDone) { ...WishlistFields }
    }
  `;
  const data = await getGraphQLClient().request<{ wishlist: GqlWishlistItem[] }>(query, {
    deckId: filters.deckId || null,
    intentId: filters.intentId || null,
    includeDone: filters.includeDone ?? false,
  });
  return data.wishlist.map(toWishlistItem);
}

/** Wishes a printing would fill (any-printing wishes for the card, or exact). */
export async function fetchWishlistForCard(cardId: string): Promise<WishlistItem[]> {
  const query = gql`
    ${WISHLIST_FIELDS}
    query GetWishlistForCard($cardId: ID!) {
      wishlistForCard(cardId: $cardId) { ...WishlistFields }
    }
  `;
  const data = await getGraphQLClient().request<{ wishlistForCard: GqlWishlistItem[] }>(query, { cardId });
  return data.wishlistForCard.map(toWishlistItem);
}

/** One deck board using a card printing. */
export interface CardDeckUse {
  deckId: string;
  deckTitle: string;
  board: 'main' | 'side' | 'maybe' | 'commander';
  quantity: number;
  setCode: string;
  foil: boolean;
}

/** Where the copies of a card (any printing) are used. */
export interface CardDeckUsage {
  owned: number;
  /** Main deck, sideboard and commander copies; maybeboards excluded. */
  inDecks: number;
  decks: CardDeckUse[];
}

export async function fetchCardDeckUsage(name: string): Promise<CardDeckUsage> {
  const query = gql`
    query GetCardDeckUsage($name: String!) {
      cardDeckUsage(name: $name) {
        owned inDecks
        decks { deckId deckTitle board quantity setCode foil }
      }
    }
  `;
  const data = await getGraphQLClient().request<{ cardDeckUsage: CardDeckUsage }>(query, { name });
  return data.cardDeckUsage;
}

/** A token, emblem or game piece a deck makes, merged across printings. */
export interface DeckToken {
  /** A printing to show (an owned one when possible); null when none is imported. */
  card: { id: string; title: string; setCode: string | null; collectorNumber: string | null; imageUri: string | null } | null;
  name: string;
  typeLine: string;
  power: string | null;
  toughness: string | null;
  oracleText: string | null;
  kind: 'token' | 'emblem' | 'game';
  /** Deck cards that make it. */
  madeBy: string[];
  /** Copies owned across printings with the same name, stats and abilities. */
  owned: number;
}

/** Tokens, emblems and game pieces of a deck's main deck, sideboard and commander. */
export async function fetchDeckTokens(deckId: string): Promise<DeckToken[]> {
  const query = gql`
    query GetDeckTokens($deckId: ID!) {
      deckTokens(deckId: $deckId) {
        name typeLine power toughness oracleText kind madeBy owned
        card { id title setCode collectorNumber imageUri }
      }
    }
  `;
  const data = await getGraphQLClient().request<{ deckTokens: DeckToken[] }>(query, { deckId });
  return data.deckTokens;
}

export async function fetchWishIntents(): Promise<WishIntent[]> {
  const query = gql`
    query GetWishIntents { wishIntents { id name } }
  `;
  const data = await getGraphQLClient().request<{ wishIntents: WishIntent[] }>(query);
  return data.wishIntents;
}

/** Wish fields to save; an omitted field keeps its stored value. */
export interface WishlistItemInput {
  id?: string | null;
  cardId: string;
  quantity: number;
  anyPrinting?: boolean;
  foil?: boolean;
  /** Empty string clears the deck. */
  deckId?: string | null;
  /** Empty string clears the intent. */
  intentId?: string | null;
  minCondition?: string | null;
  notes?: string | null;
}

export async function saveWishlistItem(input: WishlistItemInput): Promise<WishlistItem> {
  const mutation = gql`
    ${WISHLIST_FIELDS}
    mutation SaveWishlistItem(
      $id: ID, $cardId: ID!, $quantity: Int!, $anyPrinting: Boolean, $foil: Boolean,
      $deckId: ID, $intentId: ID, $minCondition: String, $notes: String
    ) {
      saveWishlistItem(
        id: $id, cardId: $cardId, quantity: $quantity, anyPrinting: $anyPrinting, foil: $foil,
        deckId: $deckId, intentId: $intentId, minCondition: $minCondition, notes: $notes
      ) { ...WishlistFields }
    }
  `;
  // Fields left undefined are dropped from the variables, so the server keeps
  // their stored value; null or '' clears them. Sending null for every
  // unchanged field wiped a wish's intent, notes and condition on each edit.
  const data = await getGraphQLClient().request<{ saveWishlistItem: GqlWishlistItem }>(mutation, {
    id: input.id ?? null,
    cardId: input.cardId,
    quantity: input.quantity,
    anyPrinting: input.anyPrinting,
    foil: input.foil,
    deckId: input.deckId,
    intentId: input.intentId,
    minCondition: input.minCondition,
    notes: input.notes,
  });
  return toWishlistItem(data.saveWishlistItem);
}

export async function deleteWishlistItem(id: string): Promise<void> {
  const mutation = gql`
    mutation DeleteWishlistItem($id: ID!) { deleteWishlistItem(id: $id) }
  `;
  await getGraphQLClient().request(mutation, { id });
}

// ---------------------------------------------------------------------------
// Collection import (exact printings by Scryfall ID)
// ---------------------------------------------------------------------------

/**
 * Matches rows to printings. With apply false nothing is written, so the
 * result can be shown for review first.
 */
export async function importCollection(
  rows: CollectionImportRow[],
  apply: boolean,
): Promise<CollectionImportResult[]> {
  const mutation = gql`
    mutation ImportCollection($rows: [CollectionImportRow!]!, $apply: Boolean!) {
      importCollection(rows: $rows, apply: $apply) {
        row status matchedBy
        card { id title setCode setName collectorNumber }
      }
    }
  `;
  const data = await getGraphQLClient().request<{ importCollection: CollectionImportResult[] }>(
    mutation,
    { rows, apply },
  );
  return data.importCollection;
}

// ---------------------------------------------------------------------------
// Deck build pool (land suggester, deck generator)
// ---------------------------------------------------------------------------

interface GqlPoolCard {
  card: GqlMtgCard;
  owned: number;
  trade: number;
  usedIn: CardUse[];
}

/**
 * Cards for deck building, one printing per card name, with owned, trade
 * and in-use counts. The cardbase source only returns lands.
 */
export async function fetchDeckBuildPool(args: {
  source: PoolSource;
  lands?: boolean | null;
  legalIn?: string | null;
  colorIdentity?: string[] | null;
  excludeDeckId?: string | null;
}): Promise<PoolCard[]> {
  const query = gql`
    ${CARD_FIELDS}
    query DeckBuildPool(
      $source: String!, $lands: Boolean, $legalIn: String,
      $colorIdentity: [String!], $excludeDeckId: ID
    ) {
      deckBuildPool(
        source: $source, lands: $lands, legalIn: $legalIn,
        colorIdentity: $colorIdentity, excludeDeckId: $excludeDeckId
      ) {
        owned trade
        usedIn { deckId deckTitle quantity }
        card { ...CardFields power toughness }
      }
    }
  `;
  const data = await getGraphQLClient().request<{ deckBuildPool: GqlPoolCard[] }>(query, {
    source: args.source,
    lands: args.lands ?? null,
    legalIn: args.legalIn ?? null,
    colorIdentity: args.colorIdentity ?? null,
    excludeDeckId: args.excludeDeckId ?? null,
  });
  return data.deckBuildPool.map(p => ({
    card: toCardResource(p.card),
    owned: p.owned,
    trade: p.trade,
    usedIn: p.usedIn,
  }));
}

/**
 * Copies of a pool card the deck builder may use.
 *
 * With includeUsed, every owned copy outside the trade binder; otherwise
 * only copies no other deck uses.
 */
export function poolCardAvailable(p: PoolCard, includeUsed: boolean): number {
  const playable = Math.max(0, p.owned - p.trade);
  if (includeUsed) {
    return playable;
  }
  const used = p.usedIn.reduce((s, u) => s + u.quantity, 0);
  return Math.max(0, playable - used);
}

// Re-export JSON:API types that are still used by other services / pages.
// These are kept in types/drupal.ts — nothing to re-export here, but the
// import above ensures the types are available for callers that do:
//   import type { ... } from '../services/drupalApi'
export type { JsonApiResource, JsonApiCollectionResponse, JsonApiSingleResponse };

// ---------------------------------------------------------------------------
// Price movers (collection ticker)
// ---------------------------------------------------------------------------

export interface PriceMover {
  card: JsonApiResource<MtgCardAttributes>;
  previous: number;
  current: number;
  /** Change in percent, e.g. 35.2 or -12.5. */
  changePct: number;
}

export interface PriceMovers {
  /** When the previous prices were captured (Unix seconds), or null. */
  since: number | null;
  movers: PriceMover[];
}

/** Biggest price movers since the previous price import, across all cards. */
export async function fetchPriceMovers(
  currency: 'EUR' | 'USD',
  limit = 10,
  minPrice = 1,
): Promise<PriceMovers> {
  const query = gql`
    ${CARD_FIELDS}
    query PriceMovers($currency: String, $limit: Int, $minPrice: Float) {
      priceMovers(currency: $currency, limit: $limit, minPrice: $minPrice) {
        since
        movers { previous current changePct card { ...CardFields } }
      }
    }
  `;
  const data = await getGraphQLClient().request<{
    priceMovers: {
      since: number | null;
      movers: { previous: number; current: number; changePct: number; card: GqlMtgCard }[];
    };
  }>(query, { currency, limit, minPrice });
  return {
    since: data.priceMovers.since,
    movers: data.priceMovers.movers.map(m => ({ ...m, card: toCardResource(m.card) })),
  };
}

// ---------------------------------------------------------------------------
// Deck shortfalls (wishlist aside)
// ---------------------------------------------------------------------------

export interface MissingDeckCard {
  /** The printing used in the deck. */
  card: JsonApiResource<MtgCardAttributes>;
  /** Copies in main deck and sideboard. */
  needed: number;
  /** Copies owned, any printing and finish. */
  owned: number;
  /** Largest wishlist quantity for this card and deck (0 when not wished). */
  wished: number;
  /** Cheapest regular price of any printing, as the wishlist uses. */
  priceEur: number | null;
  priceUsd: number | null;
}

export interface DeckShortfall {
  deckId: string;
  deckTitle: string;
  format: string;
  cards: MissingDeckCard[];
}

/** Decks whose main deck or sideboard has cards the collection does not cover. */
export async function fetchDeckShortfalls(): Promise<DeckShortfall[]> {
  const query = gql`
    ${CARD_FIELDS}
    query DeckShortfalls {
      deckShortfalls {
        deckId deckTitle format
        cards { needed owned wished priceEur priceUsd card { ...CardFields } }
      }
    }
  `;
  const data = await getGraphQLClient().request<{
    deckShortfalls: (Omit<DeckShortfall, 'cards'> & {
      cards: (Omit<MissingDeckCard, 'card'> & { card: GqlMtgCard })[];
    })[];
  }>(query);
  return data.deckShortfalls.map(d => ({
    ...d,
    cards: d.cards.map(c => ({ ...c, card: toCardResource(c.card) })),
  }));
}
