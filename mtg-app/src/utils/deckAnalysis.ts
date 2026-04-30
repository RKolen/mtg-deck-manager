/**
 * Deck analysis utility functions.
 *
 * All functions are pure and synchronous. They operate on DeckCardWithCard
 * objects (deck_card nodes with the related mtg_card attributes inlined).
 *
 * Glossary
 * --------
 * pip       — a coloured mana symbol in a casting cost, e.g. {W}, {U}
 * CMC       — converted mana cost (sum of all pips + generic)
 * source    — a permanent that can produce mana (land or mana creature)
 * effective source — lands count 1; mana-producing non-lands count 0.5 (0.5 land rule)
 */

import type { DeckCardWithCard } from '../types/drupal';

export type MtgColor = 'W' | 'U' | 'B' | 'R' | 'G';

export const ALL_COLORS: MtgColor[] = ['W', 'U', 'B', 'R', 'G'];

export const COLOR_LABEL: Record<MtgColor, string> = {
  W: 'White',
  U: 'Blue',
  B: 'Black',
  R: 'Red',
  G: 'Green',
};

// ---------------------------------------------------------------------------
// Predicates
// ---------------------------------------------------------------------------

/** Returns true when the type line indicates a land. */
export function isLand(typeLine: string): boolean {
  return /\bland\b/i.test(typeLine);
}

/**
 * Extracts a plain-string oracle text from a card attribute that may be a
 * Drupal text-format object ({ value, processed, format }) or a bare string.
 */
export function getOracleText(card: { field_oracle_text?: unknown }): string {
  const raw = card.field_oracle_text;
  if (!raw) return '';
  if (typeof raw === 'string') return raw;
  const obj = raw as { value?: string };
  return obj.value ?? '';
}

/**
 * For fetchlands — lands that sacrifice themselves to search a library for
 * another land card — Scryfall does not populate produced_mana.  We derive
 * the colours they can fetch from the basic land types named in their oracle
 * text (e.g. "Search your library for a Forest or Mountain card" → G + R).
 *
 * Returns an empty array when the oracle text does not match the fetch pattern
 * (so utility lands like Tabernacle and Maze of Ith return []).
 */
export function fetchlandColors(oracleText: string): MtgColor[] {
  const SEARCH_PATTERN =
    /sacrifice [^:]+: search your library for a .+ card, put it onto the battlefield/i;
  if (!SEARCH_PATTERN.test(oracleText)) return [];

  const LAND_TYPE_COLOR: [string, MtgColor][] = [
    ['Plains', 'W'],
    ['Island', 'U'],
    ['Swamp', 'B'],
    ['Mountain', 'R'],
    ['Forest', 'G'],
  ];
  return LAND_TYPE_COLOR
    .filter(([type]) => oracleText.includes(type))
    .map(([, color]) => color);
}

/**
 * Returns true when a land permanent can produce mana:
 * - Scryfall lists produced_mana (basics, shocks, duals, etc.), OR
 * - Its oracle text matches the fetchland search-and-fetch pattern.
 *
 * Returns false for utility lands (Tabernacle, Maze of Ith, etc.).
 */
export function landProducesMana(
  card: { field_oracle_text?: unknown; field_produced_mana?: unknown },
): boolean {
  const produced = (card.field_produced_mana ?? []) as string[];
  if (produced.length > 0) return true;
  return fetchlandColors(getOracleText(card)).length > 0;
}

/**
 * Returns the maximum number of copies of a card allowed in a deck, based on
 * the four-copy rule with these exceptions (matching Drupal's DeckCopyLimit):
 *
 *  1. "Basic Land" in type line             → unlimited (Infinity)
 *  2. "a deck can have any number" in oracle → unlimited (Infinity)
 *  3. "a deck can have up to N" in oracle    → N copies
 *  4. Default                               → 4 copies
 *
 * This rule does NOT apply to collection cards — call this only for deck cards.
 */
export function maxCopiesAllowed(
  typeLine: string,
  oracleText: string,
): number {
  if (/\bBasic\b.*\bLand\b/i.test(typeLine)) {
    return Infinity;
  }
  if (/a deck can have any number/i.test(oracleText)) {
    return Infinity;
  }
  const customMatch = oracleText.match(/a deck can have up to (\d+)/i);
  if (customMatch) {
    return parseInt(customMatch[1], 10);
  }
  return 4;
}

// ---------------------------------------------------------------------------
// Deck partitions
// ---------------------------------------------------------------------------

/** Returns main-deck cards only (excludes sideboard). */
export function mainDeck(cards: DeckCardWithCard[]): DeckCardWithCard[] {
  return cards.filter(c => !c.isSideboard);
}

/** Returns sideboard cards only. */
export function sideboard(cards: DeckCardWithCard[]): DeckCardWithCard[] {
  return cards.filter(c => c.isSideboard);
}

/** Total card count weighted by quantity. */
export function totalCount(cards: DeckCardWithCard[]): number {
  return cards.reduce((sum, c) => sum + c.quantity, 0);
}

// ---------------------------------------------------------------------------
// Mana cost parsing
// ---------------------------------------------------------------------------

/**
 * Counts the coloured pip contribution of a given colour inside a mana-cost
 * string such as "{2}{W}{W}" or "{W/U}{B}".
 *
 * - Solid pip {C}          → 1.0
 * - Hybrid pip {C1/C2}    → 0.5 each (if C is either half)
 * - Phyrexian hybrid {C/P} → 0.5 (the colour half)
 */
export function countPips(manaCost: string, color: MtgColor): number {
  let count = 0;

  // Solid pips.
  const solidRe = new RegExp(`\\{${color}\\}`, 'g');
  count += (manaCost.match(solidRe) ?? []).length;

  // Hybrid two-colour pips: {W/U}, etc.
  const hybridRe = /\{([WUBRG])\/([WUBRG])\}/g;
  let m: RegExpExecArray | null;
  while ((m = hybridRe.exec(manaCost)) !== null) {
    if (m[1] === color || m[2] === color) {
      count += 0.5;
    }
  }

  // Phyrexian hybrid pips: {W/P}, etc.
  const phyrexianRe = /\{([WUBRG])\/P\}/g;
  while ((m = phyrexianRe.exec(manaCost)) !== null) {
    if (m[1] === color) {
      count += 0.5;
    }
  }

  return count;
}

// ---------------------------------------------------------------------------
// Mana requirement
// ---------------------------------------------------------------------------

/**
 * Total coloured pip demand per colour across all non-land main-deck spells,
 * weighted by quantity.
 */
export function manaRequirement(
  cards: DeckCardWithCard[],
): Record<MtgColor, number> {
  const result: Record<MtgColor, number> = { W: 0, U: 0, B: 0, R: 0, G: 0 };

  for (const dc of mainDeck(cards)) {
    if (isLand(dc.card.field_type_line ?? '')) continue;
    const cost = dc.card.field_mana_cost ?? '';
    for (const color of ALL_COLORS) {
      result[color] += countPips(cost, color) * dc.quantity;
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Effective mana sources (with 0.5 land rule)
// ---------------------------------------------------------------------------

/**
 * Effective mana sources per colour for the main deck.
 *
 * - A land producing colour C counts as 1 source of C.
 * - A mana-producing non-land permanent (creature, artifact, enchantment,
 *   planeswalker, etc.) counts as 0.5 sources per colour it produces (the
 *   "0.5 land rule" from the spreadsheet). Covers mana dorks, mana rocks,
 *   land-producing planeswalkers (e.g. Nissa, Garruk Wildspeaker), and
 *   enchantments like Trace of Abundance. The field_is_mana_producer flag and
 *   field_produced_mana values come from Scryfall's produced_mana array, which
 *   covers all permanent types exhaustively.
 */
export function effectiveManaSources(
  cards: DeckCardWithCard[],
): Record<MtgColor, number> {
  const result: Record<MtgColor, number> = { W: 0, U: 0, B: 0, R: 0, G: 0 };

  for (const dc of mainDeck(cards)) {
    const card = dc.card;
    const produced = (card.field_produced_mana ?? []) as string[];

    if (isLand(card.field_type_line ?? '')) {
      // Use Scryfall produced_mana when available, otherwise derive colours
      // from fetchland oracle text.  Utility lands produce no colours and
      // are skipped entirely.
      const landColors =
        produced.length > 0
          ? produced
          : fetchlandColors(getOracleText(card));
      for (const color of landColors) {
        if (color in result) {
          result[color as MtgColor] += dc.quantity;
        }
      }
    } else if (card.field_is_mana_producer === true && produced.length > 0) {
      for (const color of produced) {
        if (color in result) {
          result[color as MtgColor] += dc.quantity * 0.5;
        }
      }
    }
  }

  return result;
}

/**
 * Total effective mana-producing slots in the main deck (lands count 1, all
 * other mana producers — creatures, artifacts, enchantments — count 0.5),
 * without splitting by colour.
 */
export function totalManaSources(cards: DeckCardWithCard[]): number {
  let count = 0;
  for (const dc of mainDeck(cards)) {
    const card = dc.card;
    const land = isLand(card.field_type_line ?? '');
    if (land) {
      // Exclude utility lands (Tabernacle, Maze of Ith, Emeria the Sky Ruin,
      // etc.) that genuinely do not produce mana.  Fetchlands are correctly
      // included even though Scryfall leaves their produced_mana empty.
      if (landProducesMana(card)) {
        count += dc.quantity;
      }
    } else if (card.field_is_mana_producer === true) {
      // Non-land mana producers (dorks, rocks, etc.) count as 0.5.
      count += dc.quantity * 0.5;
    }
  }
  return count;
}

// ---------------------------------------------------------------------------
// Mana color distribution
// ---------------------------------------------------------------------------

export interface ManaColorDistribution {
  /** % of effective mana sources devoted to each colour (sums to 100 over colours that have >0). */
  colorSourcePct: Record<MtgColor, number>;
  /** % of coloured-pip demand attributable to each colour (sums to 100 over colours that have >0). */
  colorPipPct: Record<MtgColor, number>;
}

/**
 * The main manabase-fit metric.
 *
 * colorSourcePct[C] = effectiveManaSources[C] / totalEffectiveSources * 100
 * colorPipPct[C]    = manaRequirement[C]       / totalPips             * 100
 *
 * When these two percentages are close for each colour the manabase matches
 * what the spells demand.
 */
export function manaColorDistribution(
  cards: DeckCardWithCard[],
): ManaColorDistribution {
  const sources = effectiveManaSources(cards);
  const pips = manaRequirement(cards);

  const totalSources = ALL_COLORS.reduce((s, c) => s + sources[c], 0);
  const totalPips = ALL_COLORS.reduce((s, c) => s + pips[c], 0);

  const colorSourcePct = {} as Record<MtgColor, number>;
  const colorPipPct = {} as Record<MtgColor, number>;

  for (const color of ALL_COLORS) {
    colorSourcePct[color] =
      totalSources > 0 ? (sources[color] / totalSources) * 100 : 0;
    colorPipPct[color] =
      totalPips > 0 ? (pips[color] / totalPips) * 100 : 0;
  }

  return { colorSourcePct, colorPipPct };
}

// ---------------------------------------------------------------------------
// Card type distribution
// ---------------------------------------------------------------------------

/** Returns the broad card category for a given type line. */
export function classifyType(typeLine: string): string {
  const lower = typeLine.toLowerCase();
  if (/\bland\b/.test(lower)) return 'Land';
  if (/creature/.test(lower)) return 'Creature';
  if (/artifact/.test(lower)) return 'Artifact';
  if (/enchantment/.test(lower)) return 'Enchantment';
  if (/planeswalker/.test(lower)) return 'Planeswalker';
  if (/instant/.test(lower)) return 'Instant';
  if (/sorcery/.test(lower)) return 'Sorcery';
  return 'Other';
}

/** Card type distribution for the main deck (quantity-weighted). */
export function cardTypeDistribution(
  cards: DeckCardWithCard[],
): Record<string, number> {
  const result: Record<string, number> = {};
  for (const dc of mainDeck(cards)) {
    const type = classifyType(dc.card.field_type_line ?? '');
    result[type] = (result[type] ?? 0) + dc.quantity;
  }
  return result;
}

// ---------------------------------------------------------------------------
// CMC histogram and average CMC
// ---------------------------------------------------------------------------

/**
 * CMC histogram for main-deck non-land cards.
 * CMC >= 7 is bucketed into the key 7.
 */
export function cmcHistogram(cards: DeckCardWithCard[]): Record<number, number> {
  const result: Record<number, number> = {};
  for (const dc of mainDeck(cards)) {
    if (isLand(dc.card.field_type_line ?? '')) continue;
    const cmc = dc.card.field_cmc ?? 0;
    const bucket = cmc >= 7 ? 7 : Math.max(0, Math.floor(cmc));
    result[bucket] = (result[bucket] ?? 0) + dc.quantity;
  }
  return result;
}

/** Weighted average CMC across all non-land main-deck cards. */
export function averageCmc(cards: DeckCardWithCard[]): number {
  let totalCmc = 0;
  let totalCards = 0;
  for (const dc of mainDeck(cards)) {
    if (isLand(dc.card.field_type_line ?? '')) continue;
    totalCmc += (dc.card.field_cmc ?? 0) * dc.quantity;
    totalCards += dc.quantity;
  }
  return totalCards > 0 ? totalCmc / totalCards : 0;
}

// ---------------------------------------------------------------------------
// Mana / coloured-card ratio
// ---------------------------------------------------------------------------

/**
 * Ratio of total effective mana sources to the number of coloured (non-land)
 * spells. A coloured spell has at least one coloured pip in its casting cost.
 */
export function manaColoredCardRatio(cards: DeckCardWithCard[]): number {
  const sources = totalManaSources(cards);
  let coloredCards = 0;
  for (const dc of mainDeck(cards)) {
    if (isLand(dc.card.field_type_line ?? '')) continue;
    const cost = dc.card.field_mana_cost ?? '';
    const pips = ALL_COLORS.reduce((s, c) => s + countPips(cost, c), 0);
    if (pips > 0) coloredCards += dc.quantity;
  }
  return coloredCards > 0 ? sources / coloredCards : 0;
}

// ---------------------------------------------------------------------------
// Hypergeometric probability
// ---------------------------------------------------------------------------

/**
 * Log factorial using a cached table for numerical stability when computing
 * hypergeometric probabilities.
 */
const LOG_FACT_CACHE: number[] = [0];

function logFactorial(n: number): number {
  if (n <= 0) return 0;
  while (LOG_FACT_CACHE.length <= n) {
    const i = LOG_FACT_CACHE.length;
    LOG_FACT_CACHE.push(
      LOG_FACT_CACHE[i - 1]! + Math.log(i),
    );
  }
  return LOG_FACT_CACHE[n]!;
}

function logBinomial(n: number, k: number): number {
  if (k < 0 || k > n) return -Infinity;
  if (k === 0 || k === n) return 0;
  return logFactorial(n) - logFactorial(k) - logFactorial(n - k);
}

/** Hypergeometric PMF: P(X = k) given population N, successes K, draws n. */
function hypergeometricPmf(
  N: number,
  K: number,
  n: number,
  k: number,
): number {
  if (k < 0 || k > K || k > n || n - k > N - K) return 0;
  return Math.exp(
    logBinomial(K, k) + logBinomial(N - K, n - k) - logBinomial(N, n),
  );
}

/**
 * P(X >= k) for the hypergeometric distribution.
 *
 * @param N - Deck size (usually 60)
 * @param K - Number of relevant sources in the deck
 * @param n - Cards seen (7 opening hand + turns drawn)
 * @param k - Minimum number of sources required
 */
export function hypergeometricAtLeast(
  N: number,
  K: number,
  n: number,
  k: number,
): number {
  if (k <= 0) return 1;
  if (K <= 0) return 0;
  const cap = Math.min(K, n);
  let prob = 0;
  for (let j = k; j <= cap; j++) {
    prob += hypergeometricPmf(N, K, n, j);
  }
  return Math.min(1, prob);
}

// ---------------------------------------------------------------------------
// Mana hand probability table
// ---------------------------------------------------------------------------

export interface ManaHandTable {
  /** Rows = turn (1–7). Columns = sources needed (1, 2, 3). */
  table: number[][];
  turns: number[];
  sourcesNeeded: number[];
}

/**
 * Returns P(drawing ≥ k sources of colour C by turn T) for T = 1..7 and
 * k = 1, 2, 3.
 *
 * Opening hand = 7 cards; turn T means 7 + (T-1) cards have been seen.
 * Effective sources are rounded to the nearest integer for the hypergeometric.
 */
export function manaHandProbability(
  cards: DeckCardWithCard[],
  color: MtgColor,
  deckSize = 60,
): ManaHandTable {
  const sources = effectiveManaSources(cards);
  const K = Math.round(sources[color]);

  const turns = [1, 2, 3, 4, 5, 6, 7];
  const sourcesNeeded = [1, 2, 3];

  const table = turns.map(turn => {
    const n = 6 + turn; // 7-card hand drawn on turn 1; +1 per subsequent turn
    return sourcesNeeded.map(k =>
      hypergeometricAtLeast(deckSize, K, n, k),
    );
  });

  return { table, turns, sourcesNeeded };
}
