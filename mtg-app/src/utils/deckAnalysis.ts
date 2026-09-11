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
  const obj = raw as { value?: string | null; processed?: string | null };
  return obj.value ?? obj.processed ?? '';
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

/** Normalize a deck format label for comparisons. */
export function normalizeFormat(format: string | null | undefined): string {
  return (format ?? '').trim().toLowerCase().replace(/[:\-]+/g, ' ').replace(/\s+/g, ' ');
}

const HUNDRED_CARD_SINGLETON = new Set([
  'edh',
  'commander',
  'predh',
  'pauper commander',
  'historic brawl',
  'gladiator',
  'canadian highlander',
  'canlander',
  'duel commander',
  'duel',
  'brawl',
]);

const SIXTY_CARD_SINGLETON = new Set(['standard brawl', 'oathbreaker']);

/** True for Commander / EDH format labels (100-card singleton). */
export function isCommanderFormat(format: string | null | undefined): boolean {
  const normalized = normalizeFormat(format);
  return normalized === 'edh' || normalized === 'commander';
}

/** True for 100-card singleton formats (Commander family, Brawl, Gladiator). */
export function isHundredCardSingleton(
  format: string | null | undefined,
): boolean {
  return HUNDRED_CARD_SINGLETON.has(normalizeFormat(format));
}

/** True for 60-card singleton formats (Standard Brawl, Oathbreaker). */
export function isSixtyCardSingleton(
  format: string | null | undefined,
): boolean {
  return SIXTY_CARD_SINGLETON.has(normalizeFormat(format));
}

/**
 * True for Tiny Leaders / Tiny Leaders: Reborn (TLR) labels (50-card singleton).
 */
export function isTinyLeadersFormat(format: string | null | undefined): boolean {
  const normalized = normalizeFormat(format);
  return (
    normalized === 'tiny leader'
    || normalized === 'tiny leaders'
    || normalized === 'tinyleaders'
    || normalized === 'tlr'
    || normalized === 'tiny leaders reborn'
  );
}

/** True for singleton commander-style formats. */
export function isSingletonFormat(format: string | null | undefined): boolean {
  return (
    isHundredCardSingleton(format)
    || isTinyLeadersFormat(format)
    || isSixtyCardSingleton(format)
  );
}

const USES_COMMANDER_CARD = new Set([
  'edh',
  'commander',
  'tiny leader',
  'tiny leaders',
  'tinyleaders',
  'tlr',
  'tiny leaders reborn',
  'duel commander',
  'pauper commander',
  'predh',
  'brawl',
  'standard brawl',
  'historic brawl',
  'oathbreaker',
]);

/** True when the format has a designated commander (or oathbreaker) card. */
export function usesCommanderCard(format: string | null | undefined): boolean {
  return USES_COMMANDER_CARD.has(normalizeFormat(format));
}

/** Tiny Leaders / TLR mana-value cap (Rule of 3). */
export const TINY_LEADERS_MAX_MANA_VALUE = 3;

/**
 * Whether a printing is a legal commander for the format.
 * Legendary creature or planeswalker, plus cards that "can be your commander".
 * Tiny Leaders also requires mana value 3 or less. Oathbreaker requires a
 * planeswalker.
 */
export function isLegalCommanderCard(
  typeLine: string,
  cmc: number | null | undefined,
  oracleText: string | null | undefined,
  format: string | null | undefined,
): boolean {
  const type = typeLine.toLowerCase();
  const oracle = (oracleText ?? '').toLowerCase();
  const canBe = /can be your commander/.test(oracle);
  const legendary = /\blegendary\b/.test(type);
  const creature = /\bcreature\b/.test(type);
  const planeswalker = /\bplaneswalker\b/.test(type);

  if (normalizeFormat(format) === 'oathbreaker') {
    return planeswalker;
  }
  const ok = (legendary && (creature || planeswalker)) || canBe;
  if (!ok) {
    return false;
  }
  if (isTinyLeadersFormat(format)) {
    return (cmc ?? 0) <= TINY_LEADERS_MAX_MANA_VALUE;
  }
  return true;
}

/**
 * Format mana-value cap for nonland cards, or null when unrestricted.
 * Tiny Leaders / TLR: every nonland card must have mana value ≤ 3.
 */
export function maxManaValueForFormat(
  format: string | null | undefined,
): number | null {
  return isTinyLeadersFormat(format) ? TINY_LEADERS_MAX_MANA_VALUE : null;
}

/**
 * Whether a card's mana value is legal for the format.
 * Lands are always allowed; nonlands must respect the format MV cap.
 */
export function isLegalManaValue(
  typeLine: string,
  cmc: number | null | undefined,
  format: string | null | undefined,
): boolean {
  const maxMv = maxManaValueForFormat(format);
  if (maxMv == null) {
    return true;
  }
  if (isLand(typeLine)) {
    return true;
  }
  return (cmc ?? 0) <= maxMv;
}

export interface DeckListAllowance {
  /** Required main-deck size (or constructed minimum). Commander is separate. */
  mainTarget: number;
  /**
   * When true, mainTarget is a hard maximum. Only cards whose oracle text
   * contains "rulebreaker" may push the list over that number.
   */
  mainHardMax: boolean;
  /**
   * Soft sideboard guidance size, or null when the format has no official
   * sideboard (Commander). Oversized boards are allowed either way.
   */
  sideboardSoftMax: number | null;
  /** Nonland mana-value cap, or null when unrestricted. */
  maxManaValue: number | null;
}

/**
 * Format-aware decklist size rules.
 * Constructed: min 60, no maximum. Commander family: exactly 99 + commander.
 * Tiny Leaders / TLR: exactly 49 + commander, soft 10-card sideboard, MV ≤ 3
 * for nonlands. Standard Brawl and Oathbreaker: exactly 59 + commander.
 */
export function deckListAllowance(format: string | null | undefined): DeckListAllowance {
  if (isHundredCardSingleton(format)) {
    return {
      mainTarget: usesCommanderCard(format) ? 99 : 100,
      mainHardMax: true,
      sideboardSoftMax: null,
      maxManaValue: null,
    };
  }
  if (isTinyLeadersFormat(format)) {
    return {
      mainTarget: 49,
      mainHardMax: true,
      sideboardSoftMax: 10,
      maxManaValue: TINY_LEADERS_MAX_MANA_VALUE,
    };
  }
  if (isSixtyCardSingleton(format)) {
    return {
      mainTarget: usesCommanderCard(format) ? 59 : 60,
      mainHardMax: true,
      sideboardSoftMax: null,
      maxManaValue: null,
    };
  }
  return {
    mainTarget: 60,
    mainHardMax: false,
    sideboardSoftMax: 15,
    maxManaValue: null,
  };
}

/** True when oracle text lets a card exceed a hard deck-size cap. */
export function hasRulebreaker(oracleText: string | null | undefined): boolean {
  return /rulebreaker/i.test(oracleText ?? '');
}

/** Main-deck copies that do not have Rulebreaker in their oracle text. */
export function nonRulebreakerMainCount(cards: DeckCardWithCard[]): number {
  return cards
    .filter(c => !c.isSideboard && !hasRulebreaker(getOracleText(c.card)))
    .reduce((sum, c) => sum + c.quantity, 0);
}

/**
 * True when a card may be added to the main deck without breaking size.
 * Constructed has no maximum. Hard-cap formats block non-Rulebreaker cards
 * once non-Rulebreaker main copies already meet the target.
 */
export function canAddToMain(
  format: string | null | undefined,
  nonRulebreakerMain: number,
  oracleText: string | null | undefined,
): boolean {
  const allowance = deckListAllowance(format);
  if (!allowance.mainHardMax) {
    return true;
  }
  if (hasRulebreaker(oracleText)) {
    return true;
  }
  return nonRulebreakerMain < allowance.mainTarget;
}

/** True when main-deck count is legal for the format. */
export function isMainDeckSizeOk(
  format: string | null | undefined,
  mainCount: number,
  options?: { nonRulebreakerCount?: number },
): boolean {
  const allowance = deckListAllowance(format);
  if (allowance.mainHardMax) {
    const nonRb = options?.nonRulebreakerCount ?? mainCount;
    return mainCount >= allowance.mainTarget && nonRb <= allowance.mainTarget;
  }
  return mainCount >= allowance.mainTarget;
}

/**
 * Returns the maximum number of copies of a card allowed in a deck, based on
 * constructed / singleton rules with these exceptions (matching Drupal's
 * DeckCopyLimit):
 *
 *  1. "Basic Land" in type line              → unlimited (Infinity)
 *  2. "a deck can have any number" in oracle → unlimited (Infinity)
 *  3. "a deck can have up to N" in oracle     → N copies
 *  4. "a deck can have only one" in oracle    → 1 copy
 *  5. Commander / EDH / Tiny Leaders / TLR   → 1 copy (singleton)
 *  6. Default constructed                    → 4 copies
 *
 * This rule does NOT apply to collection cards — call this only for deck cards.
 */
export function maxCopiesAllowed(
  typeLine: string,
  oracleText: string,
  format: string | null | undefined = null,
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
  if (/a deck can have only one/i.test(oracleText)) {
    return 1;
  }
  return isSingletonFormat(format) ? 1 : 4;
}

/**
 * Scryfall `legalities` key for a deck format label, or null when the
 * format is community-only (Tiny Leaders, Canadian Highlander, etc.).
 */
export function scryfallFormatKey(
  format: string | null | undefined,
): string | null {
  const normalized = normalizeFormat(format);
  const mapped: Record<string, string> = {
    standard: 'standard',
    pioneer: 'pioneer',
    modern: 'modern',
    legacy: 'legacy',
    vintage: 'vintage',
    pauper: 'pauper',
    historic: 'historic',
    explorer: 'explorer',
    timeless: 'timeless',
    alchemy: 'alchemy',
    premodern: 'premodern',
    'penny dreadful': 'penny',
    penny: 'penny',
    edh: 'commander',
    commander: 'commander',
    'duel commander': 'duel',
    duel: 'duel',
    brawl: 'brawl',
    'historic brawl': 'brawl',
    'standard brawl': 'standardbrawl',
    'pauper commander': 'paupercommander',
    oathbreaker: 'oathbreaker',
    predh: 'predh',
    gladiator: 'gladiator',
    'old school': 'oldschool',
    oldschool: 'oldschool',
    'tiny leader': 'tlr',
    'tiny leaders': 'tlr',
    tinyleaders: 'tlr',
    tlr: 'tlr',
    'tiny leaders reborn': 'tlr',
  };
  return mapped[normalized] ?? null;
}

export interface DeckLegalityCard {
  title: string;
  field_type_line?: string | null;
  field_cmc?: number | null;
  field_oracle_text?: unknown;
  field_legal_formats?: string[] | null;
  field_restricted_formats?: string[] | null;
}

export type DeckLegalityCode =
  | 'size'
  | 'copies'
  | 'restricted'
  | 'illegal'
  | 'mana_value'
  | 'commander';

export interface DeckLegalityIssue {
  code: DeckLegalityCode;
  message: string;
}

export interface DeckLegality {
  ok: boolean;
  issues: DeckLegalityIssue[];
}

/**
 * Copy limit including the restricted list (1) when Scryfall marks the
 * card restricted in this format.
 */
export function maxCopiesForCard(
  typeLine: string,
  oracleText: string,
  format: string | null | undefined,
  restrictedFormats: string[] | null | undefined = null,
): number {
  const base = maxCopiesAllowed(typeLine, oracleText, format);
  const key = scryfallFormatKey(format);
  if (key != null && (restrictedFormats ?? []).includes(key)) {
    return Math.min(base, 1);
  }
  return base;
}

function isPlayableInFormat(
  card: DeckLegalityCard,
  scryfallKey: string,
): boolean {
  const legal = card.field_legal_formats ?? [];
  const restricted = card.field_restricted_formats ?? [];
  return legal.includes(scryfallKey) || restricted.includes(scryfallKey);
}

/**
 * Full constructed-legality check for the decks list badge and editor.
 *
 * Enforces: main-deck size, 4-of (or singleton) by oracle name across
 * printings and main+sideboard, Vintage-style restricted list, Scryfall
 * format legality (banned / not legal), Tiny Leaders mana-value, and a
 * designated commander when the format requires one.
 */
export function evaluateDeckLegality(
  format: string | null | undefined,
  cards: DeckCardWithCard[],
  commander: DeckLegalityCard | null | undefined = null,
): DeckLegality {
  const issues: DeckLegalityIssue[] = [];
  const allowance = deckListAllowance(format);
  const mainCount = totalCount(mainDeck(cards));
  const nonRb = nonRulebreakerMainCount(cards);
  const formatLabel = (format ?? '').trim() || 'this format';
  const scryfallKey = scryfallFormatKey(format);

  if (!isMainDeckSizeOk(format, mainCount, { nonRulebreakerCount: nonRb })) {
    if (allowance.mainHardMax && nonRb > allowance.mainTarget) {
      issues.push({
        code: 'size',
        message: `Main deck has ${mainCount} cards; ${formatLabel} allows at most ${allowance.mainTarget}.`,
      });
    }
    else {
      issues.push({
        code: 'size',
        message: `Main deck has ${mainCount} cards; ${formatLabel} needs ${allowance.mainTarget}.`,
      });
    }
  }

  if (usesCommanderCard(format) && commander == null) {
    issues.push({
      code: 'commander',
      message: `Missing commander for ${formatLabel}.`,
    });
  }

  const byName = new Map<string, { qty: number; card: DeckLegalityCard }>();
  const addNamed = (card: DeckLegalityCard, qty: number) => {
    const name = card.title.trim();
    if (name === '') {
      return;
    }
    const existing = byName.get(name);
    if (existing) {
      existing.qty += qty;
      return;
    }
    byName.set(name, { qty, card });
  };

  for (const slot of cards) {
    addNamed(slot.card, slot.quantity);
  }
  if (commander != null) {
    addNamed(commander, 1);
  }

  for (const { qty, card } of byName.values()) {
    const oracle = getOracleText(card);
    const typeLine = card.field_type_line ?? '';
    const max = maxCopiesForCard(
      typeLine,
      oracle,
      format,
      card.field_restricted_formats,
    );
    if (qty > max) {
      const key = scryfallFormatKey(format);
      const restricted =
        key != null && (card.field_restricted_formats ?? []).includes(key);
      issues.push({
        code: restricted ? 'restricted' : 'copies',
        message: restricted
          ? `${qty} copies of ${card.title} (restricted to 1 in ${formatLabel}).`
          : `${qty} copies of ${card.title} (max ${max}, main and sideboard combined).`,
      });
    }

    if (
      scryfallKey != null &&
      !isPlayableInFormat(card, scryfallKey)
    ) {
      issues.push({
        code: 'illegal',
        message: `${card.title} is not legal in ${formatLabel}.`,
      });
    }
  }

  const mvSeen = new Set<string>();
  const checkManaValue = (card: DeckLegalityCard) => {
    if (isLegalManaValue(card.field_type_line ?? '', card.field_cmc, format)) {
      return;
    }
    if (mvSeen.has(card.title)) {
      return;
    }
    mvSeen.add(card.title);
    issues.push({
      code: 'mana_value',
      message: `${card.title} has mana value ${card.field_cmc ?? 0}; ${formatLabel} allows at most ${allowance.maxManaValue}.`,
    });
  };

  for (const slot of cards) {
    checkManaValue(slot.card);
  }
  if (commander != null) {
    checkManaValue(commander);
  }

  return { ok: issues.length === 0, issues };
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

  // Phyrexian hybrid pips: {W/P}, {G/P}, etc.
  // These are paid with life in practice — counted only when the deck already
  // produces that colour naturally (i.e. the caller passes the deck's colour set).
  // Since countPips is called per-colour without that context, we treat them as 0
  // because the life-payment option means no coloured mana source is needed.
  // (A dedicated RG deck with {W/P} cards pays life, never W mana.)

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

  // Determine which colours the deck's spells actually demand (non-zero pip demand).
  // Fetchlands that CAN produce B should not be attributed as B sources in a deck
  // whose spells have zero B pip demand — the player simply fetches an RG land.
  const spellPips = manaRequirement(cards);
  const deckSpellColors = new Set(
    (Object.keys(spellPips) as MtgColor[]).filter(c => spellPips[c] > 0),
  );

  for (const dc of mainDeck(cards)) {
    const card = dc.card;
    const produced = (card.field_produced_mana ?? []) as string[];

    if (isLand(card.field_type_line ?? '')) {
      const rawColors =
        produced.length > 0
          ? produced
          : fetchlandColors(getOracleText(card));

      // For fetchlands (and other flexible lands), restrict attributed colours
      // to those the deck's spells actually need. This prevents Bloodstained Mire
      // from counting as a B source in a deck that never casts B spells — the
      // player simply fetches an RG dual instead.
      const landColors =
        rawColors.length > 1
          ? rawColors.filter(c => deckSpellColors.has(c as MtgColor))
          : rawColors; // single-colour lands always count as-is

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

/** Decklist section order: one heading per card type. */
export const DECK_LIST_TYPE_GROUPS: { label: string; types: string[] }[] = [
  { label: 'Creatures', types: ['Creature'] },
  { label: 'Planeswalkers', types: ['Planeswalker'] },
  { label: 'Instants', types: ['Instant'] },
  { label: 'Sorceries', types: ['Sorcery'] },
  { label: 'Enchantments', types: ['Enchantment'] },
  { label: 'Artifacts', types: ['Artifact'] },
  { label: 'Other', types: ['Other'] },
  { label: 'Lands', types: ['Land'] },
];

/** Groups cards into non-empty type sections for a decklist. */
export function groupDeckCardsByType<T extends { card: { field_type_line?: string | null } }>(
  cards: T[],
): { label: string; cards: T[] }[] {
  return DECK_LIST_TYPE_GROUPS.map(group => ({
    label: group.label,
    cards: cards.filter(dc =>
      group.types.includes(classifyType(dc.card.field_type_line ?? '')),
    ),
  })).filter(group => group.cards.length > 0);
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
