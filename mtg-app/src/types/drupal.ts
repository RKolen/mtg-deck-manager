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
  field_oracle_text: string;
  field_scryfall_id: string;
  field_image_uri: string;
  field_is_mana_producer: boolean;
  field_produced_mana: string[];
  field_legal_formats: string[];
}

export interface DeckAttributes {
  title: string;
  field_format: string;
  field_notes: string | null;
}

// DeckCardAttributes is no longer used — decks reference mtg_card nodes
// directly via field_main_cards and field_sideboard_cards on the deck node.

export interface CollectionCardAttributes {
  field_quantity_owned: number;
  field_quantity_foil: number;
}

// Convenience resource types
export type MtgCard = JsonApiResource<MtgCardAttributes>;
export type Deck = JsonApiResource<DeckAttributes>;
export type CollectionCard = JsonApiResource<CollectionCardAttributes>;

/**
 * A card slot in a deck — one entry per copy of a card.
 * Derived from the deck's field_main_cards or field_sideboard_cards.
 */
export interface DeckCardSlot {
  /** The mtg_card node ID. */
  cardId: string;
  /** Whether this slot is in the sideboard. */
  isSideboard: boolean;
  /** Full card attributes resolved from the JSON:API include. */
  card: MtgCardAttributes & { id: string };
}

/**
 * A card grouped with its copy count — used by the analysis engine.
 * Not a Drupal resource; derived client-side from DeckCardSlot[].
 */
export interface DeckCardWithCard {
  id: string;
  quantity: number;
  isSideboard: boolean;
  card: MtgCardAttributes & { id: string };
}
