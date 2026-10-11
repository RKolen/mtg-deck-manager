import type { QueryClient } from '@tanstack/react-query';
import type { CollectionCardAttributes, JsonApiResource } from '../types/drupal';

type CollectionList = JsonApiResource<CollectionCardAttributes>[];

/** New counts for one collection row, keyed by the printing's UUID. */
export interface CollectionRowPatch {
  cardId: string;
  /** Collection row UUID, once the server has created it. */
  id?: string;
  quantityOwned: number;
  quantityFoil: number;
  quantityTrade?: number;
  binderLocation?: string | null;
}

function printingOf(cc: JsonApiResource<CollectionCardAttributes>): string | null {
  const rel = cc.relationships?.field_card?.data;
  return (Array.isArray(rel) ? rel[0]?.id : rel?.id) ?? null;
}

/**
 * Updates one row of the cached collection list in place.
 *
 * Returns false when the list is not cached or has no row for the printing
 * yet (a first copy); the caller then lets the list refetch.
 */
export function patchCollectionRow(qc: QueryClient, patch: CollectionRowPatch): boolean {
  const list = qc.getQueryData<CollectionList>(['collectionCards']);
  if (list == null) {
    return false;
  }
  const index = list.findIndex(cc => printingOf(cc) === patch.cardId);
  if (index < 0) {
    return false;
  }
  const prev = list[index]!;
  const next = [...list];
  const owned = Math.max(0, patch.quantityOwned);
  const foil = Math.max(0, patch.quantityFoil);
  next[index] = {
    ...prev,
    id: patch.id ?? prev.id,
    attributes: {
      ...prev.attributes,
      field_quantity_owned: owned,
      field_quantity_foil: foil,
      field_quantity_trade: Math.min(
        patch.quantityTrade ?? prev.attributes.field_quantity_trade ?? 0,
        owned + foil,
      ),
      field_binder_location:
        patch.binderLocation !== undefined ? patch.binderLocation || null : prev.attributes.field_binder_location,
    },
  };
  qc.setQueryData<CollectionList>(['collectionCards'], next);
  return true;
}

/**
 * Refetch collection totals and deck lists after inventory mutations.
 *
 * Printing swaps, deck edits, and collection upserts all change owned
 * copies and/or printings, so menu VAL, unique counts, and per-deck
 * prices must drop together. Wishes count owned copies, so they refetch too.
 *
 * Pass keepCollectionList when the cached collection list is already
 * correct (the changed row was patched in place, or the mutation did not
 * touch the collection), so the 2,000+ rows are not loaded again.
 */
export async function invalidateInventoryQueries(
  qc: QueryClient,
  options?: { deckId?: string; keepCollectionList?: boolean },
): Promise<void> {
  const deckKey =
    options?.deckId != null && options.deckId !== ''
      ? (['deckCards', options.deckId] as const)
      : (['deckCards'] as const);
  await Promise.all([
    qc.invalidateQueries({ queryKey: ['collectionValue'] }),
    options?.keepCollectionList ? Promise.resolve() : qc.invalidateQueries({ queryKey: ['collectionCards'] }),
    qc.invalidateQueries({ queryKey: ['collectionByCard'] }),
    qc.invalidateQueries({ queryKey: ['collectionCard'] }),
    qc.invalidateQueries({ queryKey: deckKey }),
    qc.invalidateQueries({ queryKey: ['wishlist'] }),
  ]);
}
