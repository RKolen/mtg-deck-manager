/**
 * Deck templates for the random deck generator.
 *
 * Everything format specific lives here as data, so more formats or themed
 * variants are new entries, not generator changes. A 60-card template would
 * set maxCopies to 4 and seed to 'colors'; a Brawl or Tiny Leaders one
 * changes deckSize and maxManaValue.
 */

import type { CardRole } from './cardRoles';

/** Mana value buckets used for curve targets. 6 means 6 or more. */
export type CurveBucket = 1 | 2 | 3 | 4 | 5 | 6;

export const CURVE_BUCKETS: CurveBucket[] = [1, 2, 3, 4, 5, 6];

export interface DeckTemplate {
  id: string;
  label: string;
  description: string;
  /** Deck format label, as stored on the deck node. */
  format: string;
  /** Scryfall legality key for the card pool. */
  legalIn: string;
  /** Main deck size, without the commander. */
  deckSize: number;
  /** Copies allowed of a non-basic card. */
  maxCopies: number;
  /** How the deck is anchored. Only 'commander' is implemented so far. */
  seed: 'commander' | 'colors';
  /** Starting land count; the user can change it. */
  defaultLands: number;
  /** How many cards of each role to aim for. Unlisted roles are free. */
  roles: Partial<Record<CardRole, { min: number; max: number }>>;
  /** Target share of non-land cards per mana value bucket (sums to 1). */
  curve: Record<CurveBucket, number>;
  /** Mana value cap for non-land cards, or null. */
  maxManaValue: number | null;
  /** Fewest playable non-land cards in the commander's colours to try it. */
  minPool: number;
}

export const DECK_TEMPLATES: DeckTemplate[] = [
  {
    id: 'commander-default',
    label: 'Commander (balanced)',
    description: 'A 99-card singleton deck around a random commander you own, with a standard mix of ramp, '
      + 'card draw, removal and threats.',
    format: 'Commander',
    legalIn: 'commander',
    deckSize: 99,
    maxCopies: 1,
    seed: 'commander',
    defaultLands: 37,
    roles: {
      ramp: { min: 10, max: 15 },
      draw: { min: 9, max: 14 },
      removal: { min: 8, max: 12 },
      wipe: { min: 2, max: 4 },
      finisher: { min: 2, max: 6 },
    },
    curve: { 1: 0.1, 2: 0.22, 3: 0.24, 4: 0.2, 5: 0.12, 6: 0.12 },
    maxManaValue: null,
    minPool: 80,
  },
];

export function templateById(id: string): DeckTemplate {
  const found = DECK_TEMPLATES.find(t => t.id === id);
  if (found == null) {
    throw new Error(`Unknown deck template: ${id}`);
  }
  return found;
}

export function curveBucket(cmc: number): CurveBucket {
  return Math.min(6, Math.max(1, Math.round(cmc))) as CurveBucket;
}
