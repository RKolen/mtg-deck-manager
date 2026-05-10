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
  field_power: string | null;
  field_toughness: string | null;
  field_loyalty: string | null;
  // Phase 9
  field_price_usd: string | null;
  field_price_usd_foil: string | null;
  field_price_eur: string | null;
  field_set_code: string;
  field_set_name: string;
  field_rarity: string;
  field_collector_number: string;
  field_combo_pieces: string[];
}

export interface DeckAttributes {
  title: string;
  field_format: string;
  field_notes: string | null;
  drupal_internal__nid: number;
}

// Deck cards are stored as paragraph--deck_card entities embedded in
// node--deck.field_deck_cards (entity_reference_revisions, unlimited cardinality).

export interface CollectionCardAttributes {
  field_quantity_owned: number;
  field_quantity_foil: number;
}

// Convenience resource types
export type MtgCard = JsonApiResource<MtgCardAttributes>;
export type Deck = JsonApiResource<DeckAttributes>;
export type CollectionCard = JsonApiResource<CollectionCardAttributes>;

/**
 * A card slot in a deck, backed by a paragraph--deck_card entity.
 * id is the paragraph UUID, used by the /api/deck-cards mutations.
 */
export interface DeckCardWithCard {
  id: string;
  quantity: number;
  isSideboard: boolean;
  card: MtgCardAttributes & { id: string };
}
