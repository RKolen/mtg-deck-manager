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
