/**
 * Plain card lists ("4 Card Name", one per line) for pasting into
 * Cardmarket's wants list or a deck import. The sideboard follows after a
 * blank line.
 */

export interface CardListEntry {
  name: string;
  quantity: number;
}

/** Sums quantities per card name, keeping the first spelling and order. */
export function mergeEntries(entries: CardListEntry[]): CardListEntry[] {
  const merged = new Map<string, CardListEntry>();
  for (const entry of entries) {
    if (entry.quantity < 1 || entry.name.trim() === '') {
      continue;
    }
    const key = entry.name.trim().toLowerCase();
    const existing = merged.get(key);
    if (existing != null) {
      existing.quantity += entry.quantity;
    } else {
      merged.set(key, { name: entry.name.trim(), quantity: entry.quantity });
    }
  }
  return [...merged.values()];
}

/** "4 Card Name" lines; the sideboard follows after a blank line. */
export function formatCardList(main: CardListEntry[], side: CardListEntry[] = []): string {
  const block = (entries: CardListEntry[]): string =>
    mergeEntries(entries).map(e => `${e.quantity} ${e.name}`).join('\n');
  const mainText = block(main);
  const sideText = block(side);
  if (sideText === '') {
    return mainText;
  }
  return mainText === '' ? sideText : `${mainText}\n\n${sideText}`;
}

/**
 * Copies still to buy: owned copies (any printing) are used up by the main
 * deck first, then the sideboard. With includeOwned the full list is kept.
 *
 * @param ownedByName
 *   Owned copies per lowercase card name.
 */
export function missingEntries(
  main: CardListEntry[],
  side: CardListEntry[],
  ownedByName: Map<string, number>,
  includeOwned: boolean,
): { main: CardListEntry[]; side: CardListEntry[] } {
  const mergedMain = mergeEntries(main);
  const mergedSide = mergeEntries(side);
  if (includeOwned) {
    return { main: mergedMain, side: mergedSide };
  }
  const left = new Map(ownedByName);
  const take = (entries: CardListEntry[]): CardListEntry[] =>
    entries
      .map(entry => {
        const key = entry.name.toLowerCase();
        const owned = left.get(key) ?? 0;
        const used = Math.min(owned, entry.quantity);
        left.set(key, owned - used);
        return { name: entry.name, quantity: entry.quantity - used };
      })
      .filter(entry => entry.quantity > 0);
  const missingMain = take(mergedMain);
  const missingSide = take(mergedSide);
  return { main: missingMain, side: missingSide };
}

/** Total copies in a list. */
export function countCards(entries: CardListEntry[]): number {
  return entries.reduce((sum, e) => sum + e.quantity, 0);
}
