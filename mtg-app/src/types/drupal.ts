/**
 * Shared type definitions for Drupal JSON:API resources.
 */

export interface JsonApiResource<T = Record<string, unknown>> {
  id: string;
  type: string;
  attributes: T;
  relationships?: Record<string, JsonApiRelationship>;
  links?: Record<string, { href: string }>;
}

export interface JsonApiRelationship {
  data: JsonApiResourceIdentifier | JsonApiResourceIdentifier[] | null;
  links?: Record<string, { href: string }>;
}

export interface JsonApiResourceIdentifier {
  id: string;
  type: string;
}

export interface JsonApiCollectionResponse<T> {
  data: JsonApiResource<T>[];
  meta: { count: number };
  links: {
    self: { href: string };
    next?: { href: string };
    prev?: { href: string };
  };
}

export interface JsonApiSingleResponse<T> {
  data: JsonApiResource<T>;
}

// ---------------------------------------------------------------------------
// Content type attribute shapes
// ---------------------------------------------------------------------------

export interface MtgCardAttributes {
  title: string;
  field_mana_cost: string;
  field_cmc: number;
  field_type_line: string;
  field_colors: string[];
  field_color_identity: string[];
  field_oracle_text: { value: string; format: string | null; processed: string } | null;
  field_scryfall_id: string;
  field_image_uri: string;
  field_is_mana_producer: boolean;
  field_produced_mana: string[];
  field_legal_formats: string[];
  field_restricted_formats: string[];
  field_power: string | null;
  field_toughness: string | null;
  field_loyalty: string | null;
  // Phase 9
  field_price_usd: string | null;
  field_price_usd_foil: string | null;
  field_price_eur: string | null;
  field_price_eur_foil: string | null;
  field_set_code: string;
  field_set_name: string;
  field_rarity: string;
  field_collector_number: string;
  field_combo_pieces: string[];
  field_full_art?: boolean;
  field_border_color?: string;
}

export interface DeckCommander {
  id: string;
  title: string;
  field_type_line: string;
  field_mana_cost: string;
  field_cmc: number;
  field_color_identity: string[];
  field_oracle_text: string;
  field_image_uri: string;
  field_legal_formats?: string[];
  field_restricted_formats?: string[];
  field_set_code: string;
  field_set_name: string;
  field_collector_number: string;
  field_price_usd: string | null;
  field_price_eur: string | null;
  field_price_usd_foil: string | null;
  field_price_eur_foil: string | null;
}

export interface DeckAttributes {
  title: string;
  field_format: string;
  field_notes: string | null;
  drupal_internal__nid: number;
  /** When true, value the deck with foil prices. */
  field_is_foil?: boolean;
  /** Unix timestamp from Drupal `changed`, when available. */
  changed?: number | null;
  field_commander?: DeckCommander | null;
  field_commander_foil?: boolean;
}

// Deck cards are stored as paragraph--deck_card entities embedded in
// node--deck.field_deck_cards (entity_reference_revisions, unlimited cardinality).

export interface CollectionCardAttributes {
  field_quantity_owned: number;
  field_quantity_foil: number;
  /** Copies (regular and foil together) available for trade. */
  field_quantity_trade?: number;
  /** Where the trade copies are kept, e.g. "Trade binder, page 3, pocket 7". */
  field_binder_location?: string | null;
  /** Printing title when the collection query includes card fields. */
  field_card_title?: string;
  field_set_code?: string;
  field_set_name?: string;
  field_collector_number?: string;
  field_type_line?: string;
  field_cmc?: number;
  field_price_usd?: string | null;
  field_price_eur?: string | null;
  field_price_eur_foil?: string | null;
  field_price_usd_foil?: string | null;
  field_image_uri?: string | null;
  field_full_art?: boolean;
  field_border_color?: string;
}

// Convenience resource types
export type MtgCard = JsonApiResource<MtgCardAttributes>;
export type Deck = JsonApiResource<DeckAttributes>;
export type CollectionCard = JsonApiResource<CollectionCardAttributes>;

/**
 * A card slot in a deck, backed by a paragraph--deck_card entity.
 * id is the paragraph UUID, used by the /api/deck-cards mutations.
 */
/** Where a deck slot lives: main deck, sideboard, or maybeboard. */
export type DeckBoard = 'main' | 'side' | 'maybe';

export interface DeckCardWithCard {
  id: string;
  quantity: number;
  isSideboard: boolean;
  isFoil: boolean;
  /** Maybeboard slots never count toward deck size, legality or value. */
  board: DeckBoard;
  card: MtgCardAttributes & { id: string };
}

export interface WishIntent {
  id: string;
  name: string;
}

/** Cardmarket conditions, best first. */
export const WISH_CONDITIONS = ['M', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO'] as const;
export type WishCondition = (typeof WISH_CONDITIONS)[number];

/** A wanted card. Done once the collection holds the wanted quantity. */
export interface WishlistItem {
  id: string;
  quantity: number;
  /** Any printing fills the wish; false means this exact printing. */
  anyPrinting: boolean;
  foil: boolean;
  minCondition: WishCondition | null;
  notes: string | null;
  card: (MtgCardAttributes & { id: string }) | null;
  deck: { id: string; title: string } | null;
  intent: WishIntent | null;
  /** Copies in the collection that count toward the wish. */
  owned: number;
  done: boolean;
  /** One copy in EUR: cheapest priced printing for any-printing wishes. */
  priceEur: number | null;
  /** One copy in USD: cheapest priced printing for any-printing wishes. */
  priceUsd: number | null;
}

/** One row for the collection import (matched by Scryfall ID first). */
export interface CollectionImportRow {
  name?: string | null;
  quantity: number;
  foil?: boolean;
  scryfallId?: string | null;
  setCode?: string | null;
  collectorNumber?: string | null;
  quantityTrade?: number | null;
  binderLocation?: string | null;
}

export interface CollectionImportResult {
  row: number;
  /** matched (dry run), added, skipped or not_found. */
  status: 'matched' | 'added' | 'skipped' | 'not_found';
  matchedBy: string;
  card: { id: string; title: string; setCode: string | null; setName: string | null; collectorNumber: string | null } | null;
}
