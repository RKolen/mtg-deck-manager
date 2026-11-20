/**
 * Display helpers for the collection statistics page.
 */

import type { Currency } from './prices';

/** Label for a price band, e.g. "< 0.25", "1 - 5", "100+", "no price". */
export function bandLabel(min: number | null, max: number | null): string {
  if (min == null && max == null) {
    return 'no price';
  }
  const fmt = (n: number): string => (Number.isInteger(n) ? String(n) : n.toFixed(2));
  if (max == null) {
    return `${fmt(min ?? 0)}+`;
  }
  if ((min ?? 0) === 0) {
    return `< ${fmt(max)}`;
  }
  return `${fmt(min ?? 0)} - ${fmt(max)}`;
}

/** Share as a percentage with one decimal, e.g. 0.4472 -> "44.7%". */
export function percent(share: number): string {
  if (!Number.isFinite(share)) {
    return '--';
  }
  return `${(share * 100).toFixed(1)}%`;
}

/** Share of a part in a total (0 when the total is 0). */
export function shareOf(part: number, total: number): number {
  return total > 0 ? part / total : 0;
}

/** Completion of a set as a share, capped at 1. */
export function completion(owned: number, setSize: number): number {
  return setSize > 0 ? Math.min(1, owned / setSize) : 0;
}

/**
 * Parses the cutoff input; empty or invalid input falls back to 1.
 */
export function parseCutoff(raw: string): number {
  const n = Number.parseFloat(raw.replace(',', '.'));
  return Number.isFinite(n) && n >= 0 ? n : 1;
}

/** Currency prefix used in band and cutoff labels. */
export function currencySymbol(currency: Currency): string {
  return currency === 'EUR' ? 'EUR ' : '$';
}

export type OwnFilter = 'all' | 'owned' | 'missing';

/** Deck cards for an owned filter; "missing" includes partly owned slots. */
export function filterDeckCards<T extends { status: string }>(cards: T[], filter: OwnFilter): T[] {
  if (filter === 'owned') return cards.filter(c => c.status === 'owned');
  if (filter === 'missing') return cards.filter(c => c.status !== 'owned');
  return cards;
}

export type DeckCardSort = 'board' | 'value' | 'toComplete' | 'name';

const BOARD_ORDER: Record<string, number> = { commander: 0, main: 1, side: 2 };

/** Sorts deck cards; board keeps commander, main, side order, then name. */
export function sortDeckCards<T extends {
  board: string;
  title: string;
  value: number;
  costToComplete: number;
}>(cards: T[], key: DeckCardSort): T[] {
  const rows = [...cards];
  const byName = (a: T, b: T): number => a.title.localeCompare(b.title);
  if (key === 'name') return rows.sort(byName);
  if (key === 'value') return rows.sort((a, b) => b.value - a.value || byName(a, b));
  if (key === 'toComplete') return rows.sort((a, b) => b.costToComplete - a.costToComplete || byName(a, b));
  return rows.sort((a, b) => (BOARD_ORDER[a.board] ?? 9) - (BOARD_ORDER[b.board] ?? 9) || byName(a, b));
}

/** Short board label for deck tables. */
export function boardLabel(board: string): string {
  return board === 'commander' ? 'CMD' : board === 'side' ? 'SB' : '';
}

/** Set cards for an owned filter and an optional rarity. */
export function filterSetCards<T extends { owned: boolean; rarity: string }>(
  cards: T[],
  filter: OwnFilter,
  rarity: string,
): T[] {
  return cards.filter(
    c =>
      (filter === 'all' || (filter === 'owned') === c.owned)
      && (rarity === '' || c.rarity === rarity),
  );
}

export type SetSortKey = 'value' | 'copies' | 'printings' | 'completion' | 'setName';

/** Sorts set rows by a key; names ascending, numbers descending. */
export function sortSets<T extends {
  value: number;
  copies: number;
  printings: number;
  setSize: number;
  setName: string;
}>(sets: T[], key: SetSortKey): T[] {
  const rows = [...sets];
  if (key === 'setName') {
    return rows.sort((a, b) => a.setName.localeCompare(b.setName));
  }
  const pick = (s: T): number =>
    key === 'completion' ? completion(s.printings, s.setSize) : s[key];
  return rows.sort((a, b) => pick(b) - pick(a));
}
