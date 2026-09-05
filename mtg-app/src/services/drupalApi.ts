import { gql } from 'graphql-request';
import type {
  CollectionCardAttributes,
  DeckAttributes,
  DeckCardWithCard,
  DeckCommander,
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

interface GqlComposeCollectionCard {
  id: string;
  uuid: string;
  quantityOwned: number;
  quantityFoil: number;
  card?: {
    uuid: string;
    title?: string | null;
    setCode?: string | null;
    setName?: string | null;
    collectorNumber?: string | null;
    typeLine?: string | null;
    cmc?: number | null;
    priceUsd?: string | null;
    priceEur?: string | null;
    fullArt?: boolean | null;
    borderColor?: string | null;
  } | null;
}

interface GqlDeckCard {
  id: string;
  quantity: number;
  isSideboard: boolean;
  isFoil?: boolean | null;
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

function toCollectionCardFromCompose(
  cc: GqlComposeCollectionCard,
): JsonApiResource<CollectionCardAttributes> {
  return {
    id: cc.uuid,
    type: 'node--collection_card',
    attributes: {
      field_quantity_owned: cc.quantityOwned,
      field_quantity_foil: cc.quantityFoil,
      field_card_title: cc.card?.title ?? '',
      field_set_code: cc.card?.setCode ?? '',
      field_set_name: cc.card?.setName ?? '',
      field_collector_number: cc.card?.collectorNumber ?? '',
      field_type_line: cc.card?.typeLine ?? '',
      field_cmc: cc.card?.cmc ?? 0,
      field_price_usd: cc.card?.priceUsd ?? null,
      field_price_eur: cc.card?.priceEur ?? null,
      field_full_art: Boolean(cc.card?.fullArt),
      field_border_color: cc.card?.borderColor ?? '',
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
    isFoil: Boolean(d.isFoil),
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
    priceUsd priceUsdFoil priceEur priceEurFoil setCode setName rarity collectorNumber
    fullArt borderColor
  }
`;

const CARD_DETAIL_FIELDS = gql`
  fragment CardDetailFields on MtgCard {
    id title manaCost cmc typeLine colors colorIdentity
    oracleText imageUri isManaProducer producedMana legalFormats
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

function toDeckCardFromCompose(slot: GqlComposeDeckCard): DeckCardWithCard {
  if (slot.card == null) {
    throw new Error('Deck card paragraph is missing its card reference');
  }
  const mapped = toDeckCardWithCard({
    id: slot.uuid,
    quantity: slot.quantity,
    isSideboard: slot.isSideboard,
    isFoil: Boolean(slot.isFoil),
    card: composeMtgCardToGql(slot.card),
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
          ... on ParagraphDeckCard {
            ...ComposeDeckCardFields
          }
        }
      }
    }
  `;
  const data = await getGraphQLClient().request<{
    nodeDeck: { deckCards: (GqlComposeDeckCard | null)[] } | null;
  }>(query, { id: deckId });
  const slots = data.nodeDeck?.deckCards ?? [];
  return slots
    .filter((s): s is GqlComposeDeckCard => s != null && s.card != null)
    .map(toDeckCardFromCompose);
}

async function deckCardAdd(
  deckId: string,
  cardId: string,
  quantity: number,
  isSideboard: boolean,
  foil?: boolean,
): Promise<void> {
  const mutation = gql`
    mutation DeckCardAdd(
      $deckId: ID!, $cardId: ID!, $quantity: Int!, $isSideboard: Boolean!, $foil: Boolean
    ) {
      deckCardAdd(
        deckId: $deckId, cardId: $cardId, quantity: $quantity,
        isSideboard: $isSideboard, foil: $foil
      ) { id }
    }
  `;
  await getGraphQLClient().request(mutation, {
    deckId,
    cardId,
    quantity,
    isSideboard,
    foil: foil ?? null,
  });
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
): Promise<void> {
  const existing = existingSlots.find(
    s => s.card.id === cardId && s.isSideboard === isSideboard,
  );

  if (existing != null) {
    await setCardQuantityInDeck(existing.id, existing.quantity + 1, deckId, existingSlots);
    return;
  }

  await deckCardAdd(deckId, cardId, 1, isSideboard, foil);
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
    query GetCollectionCards($after: Cursor) {
      nodeCollectionCards(first: 100, after: $after) {
        nodes {
          id uuid quantityOwned quantityFoil
          card {
            ... on NodeMtgCard {
              uuid
              title
              setCode
              setName
              collectorNumber
              typeLine
              cmc
              priceUsd
              priceEur
              fullArt
              borderColor
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  `;
  const out: JsonApiResource<CollectionCardAttributes>[] = [];
  let after: string | null = null;
  for (let page = 0; page < 50; page += 1) {
    const data = await getGraphQLClient().request<{
      nodeCollectionCards: {
        nodes: GqlComposeCollectionCard[];
        pageInfo: { hasNextPage: boolean; endCursor?: string | null };
      };
    }>(query, { after });
    const conn = data.nodeCollectionCards;
    out.push(...conn.nodes.map(toCollectionCardFromCompose));
    if (!conn.pageInfo.hasNextPage || conn.pageInfo.endCursor == null) {
      break;
    }
    after = conn.pageInfo.endCursor;
  }
  return out;
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

export async function fetchCollectionValue(currency: 'USD' | 'EUR' = 'USD'): Promise<number> {
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
