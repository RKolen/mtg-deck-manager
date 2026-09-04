import type { QueryClient } from '@tanstack/react-query';

/**
 * Refetch collection totals and deck lists after inventory mutations.
 *
 * Printing swaps, deck edits, and collection upserts all change owned
 * copies and/or printings, so menu VAL, unique counts, and per-deck
 * prices must drop together.
 */
export async function invalidateInventoryQueries(
  qc: QueryClient,
  options?: { deckId?: string },
): Promise<void> {
  const deckKey =
    options?.deckId != null && options.deckId !== ''
      ? (['deckCards', options.deckId] as const)
      : (['deckCards'] as const);
  await Promise.all([
    qc.invalidateQueries({ queryKey: ['collectionValue'] }),
    qc.invalidateQueries({ queryKey: ['collectionCards'] }),
    qc.invalidateQueries({ queryKey: ['collectionByCard'] }),
    qc.invalidateQueries({ queryKey: ['collectionCard'] }),
    qc.invalidateQueries({ queryKey: deckKey }),
  ]);
}
