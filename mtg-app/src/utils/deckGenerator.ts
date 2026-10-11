/**
 * Random deck generator.
 *
 * Builds a deck from owned cards with code, not AI: a template sets role
 * quotas and a mana curve, a FitScorer says how well each card suits the
 * commander, and weighted random picks fill the quotas. A seeded random
 * number generator makes every result reproducible.
 */

import { ALL_COLORS, type MtgColor } from './deckAnalysis';
import { cardRoles, type CardRole, type RoleCard } from './cardRoles';
import { curveBucket, type CurveBucket, type DeckTemplate } from './deckTemplates';

/** A card the generator may use. */
export interface GenCard extends RoleCard {
  id: string;
  manaCost: string;
  colorIdentity: string[];
  /** Copies the generator may use. */
  available: number;
  /** Colours of mana it can produce (rocks and dorks). */
  producedMana?: string[];
  /** Other decks this card is played in. */
  playedIn?: number;
}

export interface GeneratorInput {
  template: DeckTemplate;
  commander: GenCard;
  /** Non-land cards to choose from (the commander may be among them). */
  pool: GenCard[];
  /** Fit scores (0-1) keyed by title; missing titles count as 0. */
  fit: Map<string, number>;
  /** Number of non-land cards to pick. */
  spellCount: number;
  /** 0 = always the best fitting cards, 1 = close to uniform random. */
  chaos: number;
  seed: number;
}

export interface GeneratedCard {
  card: GenCard;
  roles: CardRole[];
  fit: number;
  /** Why it was picked: a role quota, or the curve/synergy fill. */
  reason: CardRole | 'synergy';
}

export interface GeneratedDeck {
  commander: GenCard;
  cards: GeneratedCard[];
  roleCounts: Record<CardRole, number>;
  curve: Record<CurveBucket, number>;
  /** Problems worth showing, e.g. too few cards for a quota. */
  warnings: string[];
}

// ---------------------------------------------------------------------------
// Random numbers
// ---------------------------------------------------------------------------

/** Mulberry32: small, fast, seedable. Returns floats in [0, 1). */
export function seededRandom(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A fresh seed for a new random deck. */
export function newSeed(): number {
  return Math.floor(Math.random() * 2 ** 31);
}

/** Picks one item with probability proportional to its weight. */
export function weightedPick<T>(items: T[], weight: (item: T) => number, rand: () => number): T | null {
  let total = 0;
  const weights = items.map(item => {
    const w = Math.max(0, weight(item));
    total += w;
    return w;
  });
  if (total <= 0) {
    return null;
  }
  let r = rand() * total;
  for (let i = 0; i < items.length; i++) {
    r -= weights[i]!;
    if (r < 0) {
      return items[i]!;
    }
  }
  return items[items.length - 1] ?? null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** True when every colour of the card's identity is in the allowed colours. */
export function fitsIdentity(cardIdentity: string[], allowed: string[]): boolean {
  return cardIdentity.every(c => allowed.includes(c));
}

/**
 * Commanders the generator can build around: legal commanders with enough
 * playable cards in their colours.
 */
export function eligibleCommanders(
  candidates: GenCard[],
  pool: GenCard[],
  minPool: number,
): { commander: GenCard; poolSize: number }[] {
  return candidates
    .filter(c => c.available > 0)
    .map(commander => ({
      commander,
      poolSize: pool.filter(p => p.title !== commander.title && fitsIdentity(p.colorIdentity, commander.colorIdentity))
        .length,
    }))
    .filter(e => e.poolSize >= minPool);
}

/**
 * Weight for a card's fit. Chaos 0 strongly prefers the best fits; chaos 1
 * makes every card about equally likely.
 */
function fitWeight(fit: number, chaos: number): number {
  // Chaos 0.3: a full-fit card is about 25x as likely as an unrelated one;
  // chaos 1: about 1.9x.
  const c = Math.max(0, Math.min(1, chaos));
  const temperature = 0.05 + 1.5 * c * c;
  return Math.exp(fit / temperature);
}

/** Fit bonus for cards already played in other decks: a sign they are good. */
const PLAYED_BONUS = 0.2;

function emptyRoles(): Record<CardRole, number> {
  return { ramp: 0, draw: 0, removal: 0, wipe: 0, threat: 0, finisher: 0 };
}

function emptyCurve(): Record<CurveBucket, number> {
  return { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0 };
}

// ---------------------------------------------------------------------------
// Generator
// ---------------------------------------------------------------------------

/** Generates a deck. Pure apart from the seeded random numbers. */
export function generateDeck(input: GeneratorInput): GeneratedDeck {
  const { template, commander, fit, chaos } = input;
  const rand = seededRandom(input.seed);
  const identity = commander.colorIdentity;
  const warnings: string[] = [];

  const candidates = input.pool
    .filter(c => c.title !== commander.title)
    .filter(c => c.available > 0)
    .filter(c => fitsIdentity(c.colorIdentity, identity))
    .filter(c => template.maxManaValue == null || c.cmc <= template.maxManaValue)
    .map(card => ({
      card,
      roles: cardRoles(card),
      fit: Math.min(1, (fit.get(card.title) ?? 0) + ((card.playedIn ?? 0) > 0 ? PLAYED_BONUS : 0)),
    }));

  const chosen: GeneratedCard[] = [];
  const copies = new Map<string, number>();
  const roleCounts = emptyRoles();
  const curve = emptyCurve();

  const canTake = (c: (typeof candidates)[number]): boolean => {
    const limit = Math.min(c.card.available, template.maxCopies);
    if ((copies.get(c.card.title) ?? 0) >= limit) {
      return false;
    }
    // Do not overshoot a role's maximum (a fifth board wipe).
    return c.roles.every(r => {
      const quota = template.roles[r];
      return quota == null || roleCounts[r] < quota.max;
    });
  };

  const take = (c: (typeof candidates)[number], reason: CardRole | 'synergy'): void => {
    chosen.push({ card: c.card, roles: c.roles, fit: c.fit, reason });
    copies.set(c.card.title, (copies.get(c.card.title) ?? 0) + 1);
    for (const r of c.roles) {
      roleCounts[r] += 1;
    }
    curve[curveBucket(c.card.cmc)] += 1;
  };

  /** Prefers mana values the curve still needs. */
  const curveFactor = (cmc: number): number => {
    const bucket = curveBucket(cmc);
    const wanted = template.curve[bucket] * input.spellCount;
    if (wanted <= 0) {
      return 0.2;
    }
    const filled = curve[bucket] / wanted;
    return Math.max(0.15, Math.min(2, 1.5 - filled));
  };

  // 1. Role quotas, scarcest roles first so they get first pick.
  const quotaRoles = (Object.keys(template.roles) as CardRole[])
    .sort((a, b) =>
      candidates.filter(c => c.roles.includes(a)).length - candidates.filter(c => c.roles.includes(b)).length);
  for (const role of quotaRoles) {
    const quota = template.roles[role]!;
    while (roleCounts[role] < quota.min && chosen.length < input.spellCount) {
      const options = candidates.filter(c => c.roles.includes(role) && canTake(c));
      const pick = weightedPick(options, c => fitWeight(c.fit, chaos) * curveFactor(c.card.cmc), rand);
      if (pick == null) {
        warnings.push(`Only ${roleCounts[role]} ${role} cards available (wanted ${quota.min}).`);
        break;
      }
      take(pick, role);
    }
  }

  // 2. Fill the rest by fit and curve.
  while (chosen.length < input.spellCount) {
    const options = candidates.filter(canTake);
    const pick = weightedPick(options, c => fitWeight(c.fit, chaos) * curveFactor(c.card.cmc), rand);
    if (pick == null) {
      warnings.push(`Ran out of cards: ${chosen.length} of ${input.spellCount} non-land cards picked.`);
      break;
    }
    take(pick, 'synergy');
  }

  const order: Record<string, number> = { ramp: 0, draw: 1, removal: 2, wipe: 3, finisher: 4, threat: 5, synergy: 6 };
  chosen.sort((a, b) => (order[a.reason] ?? 9) - (order[b.reason] ?? 9) || a.card.cmc - b.card.cmc
    || a.card.title.localeCompare(b.card.title));

  return { commander, cards: chosen, roleCounts, curve, warnings };
}

/** Colours of a commander's identity in WUBRG order. */
export function identityColors(card: GenCard): MtgColor[] {
  return ALL_COLORS.filter(c => card.colorIdentity.includes(c));
}

