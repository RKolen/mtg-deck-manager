/**
 * Land base suggestion.
 *
 * Pure functions: given a deck's spells, its current lands and a pool of
 * candidate lands, propose a land base. No AI and no network.
 *
 * 1. Land count: Frank Karsten's regression on average mana value and cheap
 *    ramp/draw (99-card and 60-card versions, scaled for other sizes).
 * 2. Source target per colour: the fewest sources so that the most
 *    demanding spell of that colour is castable on curve at least 90% of the
 *    time, given that the land drops were hit (Karsten's criterion, on the
 *    play, no mulligans). Calibrated within one source of his 60-card table.
 * 3. Non-land mana producers count 0.5 source per colour, as elsewhere in the
 *    app; the lands cover the rest.
 * 4. Lands are picked one at a time by how much they close the remaining
 *    shortfall, weighted by how fast they enter. Basics are unlimited and
 *    win ties.
 */

import { ALL_COLORS, logBinomial, type MtgColor } from './deckAnalysis';
import { isCheapRampOrDraw, type RoleCard } from './cardRoles';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** The land fields the suggester reads. */
export interface LandInfo {
  title: string;
  typeLine: string;
  oracleText: string;
  producedMana: string[];
}

/** A non-land main deck card (or the commander). */
export interface SpellInfo extends RoleCard {
  manaCost: string;
  producedMana: string[];
  quantity: number;
}

export type LandSpeed = 'untapped' | 'conditional' | 'tapped';

export type LandKind = 'basic' | 'fetch' | 'rainbow' | 'tri' | 'dual' | 'mono' | 'utility';

export interface LandProfile {
  /** Deck colours this land can make. */
  colors: MtgColor[];
  speed: LandSpeed;
  kind: LandKind;
  /** Costs life every time it taps for coloured mana. */
  painful: boolean;
  /** Coloured mana needs extra mana (filter lands). */
  costed: boolean;
}

/** A land the suggester may pick. */
export interface LandOption {
  land: LandInfo;
  /** Printing to add to the deck, or null to look one up (basics). */
  cardId: string | null;
  /** Copies the suggester may use (Infinity for basics and the cardbase). */
  available: number;
  /** Copies owned and not used in other decks or the trade binder. */
  free: number;
  /** Copies owned in total (minus trade copies). */
  owned: number;
  /** Titles of other decks using this card. */
  usedIn: string[];
  price: number | null;
}

/** A land already in the deck. */
export interface CurrentLand {
  land: LandInfo;
  quantity: number;
}

export interface LandBaseInput {
  spells: SpellInfo[];
  commander: SpellInfo | null;
  currentLands: CurrentLand[];
  /** Candidate non-basic lands. Basics are added automatically. */
  options: LandOption[];
  /** Colours the deck plays (commander colour identity in Commander). */
  deckColors: MtgColor[];
  /** Library size: 99 for Commander, 60 for constructed. */
  deckSize: number;
  /** Copies allowed of a non-basic land (1 in singleton formats). */
  maxCopies: number;
  /** True in Commander-style multiplayer formats. */
  commanderFormat: boolean;
  /** Fixed land count instead of the formula. */
  landCountOverride?: number | null;
}

export interface ColorTarget {
  color: MtgColor;
  /** Effective sources wanted (lands plus 0.5 per non-land producer). */
  target: number;
  /** The spell that sets the target. */
  driver: { title: string; pips: number; turn: number } | null;
  /** True when even all lands making this colour would not reach 90%. */
  unreachable: boolean;
  fromProducers: number;
  current: number;
  proposed: number;
  /** P(casting the driver on curve) with the current and proposed lands. */
  probCurrent: number;
  probProposed: number;
}

export interface LandPick {
  option: LandOption;
  profile: LandProfile;
  quantity: number;
  /** Copies not covered by free owned copies (0 for basics). */
  missing: number;
  /** True for utility lands kept from the current deck. */
  kept: boolean;
}

export interface LandBasePlan {
  landCount: number;
  landCountFormula: string;
  avgCmc: number;
  cheapRampDraw: number;
  currentLandCount: number;
  /** Share (0-1) of coloured spell requirements castable on curve. */
  castableCurrent: number;
  castableProposed: number;
  targets: ColorTarget[];
  picks: LandPick[];
  add: { title: string; quantity: number }[];
  remove: { title: string; quantity: number }[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Required chance to cast the most demanding spell of a colour on curve. */
export const CAST_PROBABILITY_GOAL = 0.9;

export const BASIC_FOR_COLOR: Record<MtgColor, string> = {
  W: 'Plains',
  U: 'Island',
  B: 'Swamp',
  R: 'Mountain',
  G: 'Forest',
};

const SPEED_FACTOR: Record<LandSpeed, number> = {
  untapped: 1,
  conditional: 0.85,
  tapped: 0.6,
};

/** Each tapped land picked makes the next one less attractive. */
const TAPPED_DECAY = 0.9;

/** Painlands and Mana Confluence: slightly worse than a clean source. */
const PAIN_FACTOR = 0.92;

/** Filter lands ({1}, {T}: Add any colour): a last resort for fixing. */
const COSTED_FACTOR = 0.3;

/** In cardbase mode, lands you already own win near ties. */
const OWNED_BONUS = 1.03;

/**
 * Tie-breaker once every spell is castable: spread spare slots by pip share.
 * Tiny next to the castability gain of a source that still matters.
 */
const SURPLUS_WEIGHT = 1e-4;

// ---------------------------------------------------------------------------
// Land profiles
// ---------------------------------------------------------------------------

function isColor(value: string): value is MtgColor {
  return (ALL_COLORS as string[]).includes(value);
}

/** One "{T}: Add ..." ability of a land. */
interface ManaAbility {
  /** Colours it makes; 'any' for any colour (or the commander's colours). */
  colors: MtgColor[] | 'any';
  /** Needs extra mana to activate (filter lands such as Shimmering Grotto). */
  costed: boolean;
  /** Depends on other lands (Exotic Orchard, Reflecting Pool). */
  conditional: boolean;
}

/**
 * Mana restrictions that make an ability useless as a general colour source:
 * Cavern of Souls, Mirrex, Serra's Sanctum, Baldur's Gate, Rhystic Cave,
 * Gond Gate.
 */
const RESTRICTED_MANA = new RegExp([
  'spend this mana only',
  'activate only',
  'unless any player pays',
  'for each',
  'where x',
  'add x mana',
  'a gate you control',
  // The Grey Havens, Plaza of Heroes, Paliano, Pit of Offerings, Gemstone Caverns.
  'any color among',
  'as you drafted',
  "exiled cards' colors",
  'luck counter',
].join('|'));

/** Lands you cannot keep: Lotus Vale, Rainbow Vale. */
const UNKEEPABLE = /would enter, sacrifice|opponent gains control of this land/;

/** Lands that skip untap steps: Pinecrest Ridge, Forsaken City, River Delta. */
const SKIPS_UNTAP = /doesn'?t untap during/;

/** Lands that can be lost: Glimmervoid, Thran Quarry. */
const MAY_BE_SACRIFICED = /if you control no \w+, sacrifice this land/;

/**
 * Reads the tap-for-mana abilities from oracle text.
 *
 * Scryfall's produced_mana lists every colour a land can ever make, which
 * makes filter lands and restricted lands look like perfect rainbow lands.
 * One-shot abilities (sacrifice, remove a counter) are skipped too.
 */
function manaAbilities(text: string, commanderFormat: boolean): ManaAbility[] {
  const result: ManaAbility[] = [];
  for (const rawLine of text.split('\n')) {
    // Typed duals only have reminder text: "({T}: Add {W} or {U}.)".
    const line = rawLine.replace(/[()]/g, '').trim();
    const colon = line.indexOf(':');
    if (colon < 0) {
      continue;
    }
    const cost = line.slice(0, colon);
    const effect = line.slice(colon + 1);
    // Abilities granted to other permanents (Forgotten Monument) are quoted.
    if (!cost.includes('{t}') || cost.includes('"') || !/\badd\b/.test(effect) || RESTRICTED_MANA.test(effect)) {
      continue;
    }
    const extraCost = cost.replace('{t}', '').replace(/pay \d+ life/, '');
    // One-shot or limited costs: sacrifice, counters, energy.
    if (/sacrifice|remove|exile|tap an untapped|discard|\{e\}/.test(extraCost)) {
      continue;
    }
    if (/commander's color identity/.test(effect) && !commanderFormat) {
      continue;
    }
    const anyColor = /any color|any type|any one color|chosen color|commander's color identity/.test(effect);
    const colors = anyColor
      ? 'any'
      : ALL_COLORS.filter(c => effect.includes(`{${c.toLowerCase()}}`));
    if (colors !== 'any' && colors.length === 0) {
      continue;
    }
    result.push({
      colors,
      // Any mana symbol left in the cost, hybrid included (Fetid Heath).
      costed: /\{[^}]+\}/.test(extraCost),
      conditional: /could produce/.test(effect),
    });
  }
  return result;
}

/** Classifies a land for a deck playing the given colours. */
export function landProfile(land: LandInfo, deckColors: MtgColor[], commanderFormat: boolean): LandProfile {
  const text = land.oracleText.toLowerCase();
  const isBasic = /\bbasic\b/i.test(land.typeLine);
  const entersTapped = /(?:this land|it) enters (?:the battlefield )?tapped\./.test(text)
    || /^this land enters tapped\.?$/m.test(text);

  // Fetches: Evolving Wilds, Prismatic Vista, Flooded Strand, Grasslands.
  // Landcycling (Ash Barrens) and Demolition Field are not fetches.
  const fetch = text.match(
    /^([^\n:]*)sacrifice this land[^\n:]*: search your library for [^.\n]*\b(?:land|plains|island|swamp|mountain|forest) card[^\n]*/m,
  );
  if (fetch != null) {
    const ability = fetch[0];
    const fetched = /basic land card/.test(ability)
      ? deckColors
      : deckColors.filter(c => ability.includes(BASIC_FOR_COLOR[c].toLowerCase()));
    let speed: LandSpeed = 'untapped';
    if (/onto the battlefield tapped/.test(ability)) {
      speed = /untap that land/.test(ability) ? 'conditional' : 'tapped';
    }
    if (entersTapped || /\{\d+\}/.test(fetch[1] ?? '')) {
      speed = 'tapped';
    }
    return {
      colors: fetched,
      speed,
      kind: fetched.length > 0 ? 'fetch' : 'utility',
      painful: false,
      costed: false,
    };
  }

  const abilities = UNKEEPABLE.test(text) ? [] : manaAbilities(text, commanderFormat);
  const colorsOf = (list: ManaAbility[]): MtgColor[] =>
    deckColors.filter(c => list.some(a => a.colors === 'any' || a.colors.includes(c)));
  const clean = abilities.filter(a => !a.costed);
  let colors = colorsOf(clean);
  if (isBasic && abilities.length === 0) {
    // Basics with odd or missing oracle text still make their colour.
    colors = deckColors.filter(c => (land.producedMana ?? []).includes(c));
  }
  let costed = false;
  if (colors.length === 0) {
    colors = colorsOf(abilities);
    costed = colors.length > 0;
  }
  const anyColor = abilities.some(a => !a.costed && a.colors === 'any');
  const painful = /deals \d+ damage to you|pay 1 life:/.test(text);

  let speed: LandSpeed = 'untapped';
  if (/pay \d+ life\. if you don'?t, it enters (?:the battlefield )?tapped/.test(text)) {
    speed = 'untapped';
  }
  else if (/unless you have two or more opponents/.test(text)) {
    speed = commanderFormat ? 'untapped' : 'tapped';
  }
  else if (/enters (?:the battlefield )?tapped unless/.test(text)) {
    speed = 'conditional';
  }
  else if (/enters (?:the battlefield )?tapped/.test(text) || SKIPS_UNTAP.test(text)) {
    speed = 'tapped';
  }
  else if (
    clean.some(a => a.conditional)
    || MAY_BE_SACRIFICED.test(text)
    // Forbidden Orchard feeds the opponent.
    || /target opponent creates/.test(text)
    || /sacrifice it unless you return/.test(text)
    || /return this land to its owner's hand/.test(text)
  ) {
    // Exotic Orchard, Reflecting Pool, Lairs, Undiscovered Paradise.
    speed = 'conditional';
  }

  let kind: LandKind;
  if (isBasic) {
    kind = 'basic';
  }
  else if (colors.length === 0) {
    kind = 'utility';
  }
  else if (anyColor && deckColors.length > 1) {
    kind = 'rainbow';
  }
  else if (colors.length >= 3) {
    kind = 'tri';
  }
  else if (colors.length === 2) {
    kind = 'dual';
  }
  else {
    kind = 'mono';
  }

  return { colors, speed, kind, painful, costed };
}

// ---------------------------------------------------------------------------
// Probability
// ---------------------------------------------------------------------------

/**
 * P(at least `pips` sources of a colour by `turn`, given at least `turn`
 * lands by then), on the play.
 *
 * @param deckSize - Library size (60, 99, ...).
 * @param lands - Lands in the deck.
 * @param sources - Lands that make the colour (capped at `lands`).
 * @param pips - Coloured pips of the spell.
 * @param turn - Turn the spell should be cast (its mana value, 1-7).
 */
export function castOnCurveProbability(
  deckSize: number,
  lands: number,
  sources: number,
  pips: number,
  turn: number,
): number {
  const N = Math.max(1, Math.round(deckSize));
  const L = Math.max(0, Math.min(N, Math.round(lands)));
  const K = Math.max(0, Math.min(L, Math.round(sources)));
  const seen = Math.min(N, 7 + turn - 1);
  const total = logBinomial(N, seen);

  let hitLandDrops = 0;
  let castable = 0;
  for (let a = 0; a <= Math.min(K, seen); a++) {
    for (let b = 0; b <= Math.min(L - K, seen - a); b++) {
      if (a + b < turn) {
        continue;
      }
      const p = Math.exp(
        logBinomial(K, a) + logBinomial(L - K, b) + logBinomial(N - L, seen - a - b) - total,
      );
      hitLandDrops += p;
      if (a >= pips) {
        castable += p;
      }
    }
  }
  return hitLandDrops > 0 ? castable / hitLandDrops : 0;
}

/**
 * Fewest sources reaching CAST_PROBABILITY_GOAL, or `lands` with
 * `unreachable` set when no count does.
 */
export function sourcesNeeded(
  deckSize: number,
  lands: number,
  pips: number,
  turn: number,
): { sources: number; unreachable: boolean } {
  for (let k = pips; k <= lands; k++) {
    if (castOnCurveProbability(deckSize, lands, k, pips, turn) >= CAST_PROBABILITY_GOAL) {
      return { sources: k, unreachable: false };
    }
  }
  return { sources: lands, unreachable: true };
}

// ---------------------------------------------------------------------------
// Land count
// ---------------------------------------------------------------------------

/** Plain coloured pips of one colour (hybrid and Phyrexian pips are flexible). */
export function solidPips(manaCost: string, color: MtgColor): number {
  return (manaCost.match(new RegExp(`\\{${color}\\}`, 'g')) ?? []).length;
}

/**
 * Karsten's land count regression.
 *
 * 99-card: 31.42 + 3.13 * avgMV - 0.28 * cheapRampDraw.
 * 60-card: 19.59 + 1.90 * avgMV - 0.28 * cheapRampDraw.
 * Other sizes scale the closer of the two. Clamped to 28-47% of the deck.
 */
export function recommendedLandCount(
  avgCmc: number,
  cheapRampDraw: number,
  deckSize: number,
): { count: number; formula: string } {
  const big = deckSize >= 80;
  const raw = big
    ? (31.42 + 3.13 * avgCmc - 0.28 * cheapRampDraw) * (deckSize / 99)
    : (19.59 + 1.9 * avgCmc - 0.28 * cheapRampDraw) * (deckSize / 60);
  const min = Math.ceil(deckSize * 0.28);
  const max = Math.floor(deckSize * 0.47);
  const count = Math.min(max, Math.max(min, Math.round(raw)));
  const base = big ? '31.42 + 3.13 x avg MV - 0.28 x cheap ramp/draw' : '19.59 + 1.90 x avg MV - 0.28 x cheap ramp/draw';
  const scale = big ? deckSize / 99 : deckSize / 60;
  const formula = scale === 1 ? base : `(${base}) x ${scale.toFixed(2)}`;
  return { count, formula };
}

// ---------------------------------------------------------------------------
// Planning
// ---------------------------------------------------------------------------

interface Requirement {
  color: MtgColor;
  title: string;
  pips: number;
  turn: number;
  /** Copies of the spell. */
  weight: number;
}

function requirements(spells: SpellInfo[], colors: MtgColor[]): Requirement[] {
  const result: Requirement[] = [];
  for (const spell of spells) {
    const turn = Math.min(7, Math.max(1, Math.round(spell.cmc)));
    for (const color of colors) {
      const pips = solidPips(spell.manaCost, color);
      if (pips > 0) {
        result.push({ color, title: spell.title, pips, turn, weight: spell.quantity });
      }
    }
  }
  return result;
}

/**
 * Share of the deck's coloured spell requirements castable on curve, per
 * colour, as a function of that colour's (possibly fractional) sources.
 *
 * Summing the result over colours gives the expected share of all
 * requirements met; the greedy fill maximises that.
 */
function castableValue(
  deckSize: number,
  lands: number,
  reqs: Requirement[],
  colors: MtgColor[],
): (color: MtgColor, sources: number) => number {
  const totalWeight = reqs.reduce((s, r) => s + r.weight, 0) || 1;
  const grouped = new Map<MtgColor, Map<string, { pips: number; turn: number; weight: number }>>();
  for (const color of colors) {
    grouped.set(color, new Map());
  }
  for (const r of reqs) {
    const byKey = grouped.get(r.color)!;
    const key = `${r.pips}:${r.turn}`;
    const entry = byKey.get(key) ?? { pips: r.pips, turn: r.turn, weight: 0 };
    entry.weight += r.weight;
    byKey.set(key, entry);
  }

  const cache = new Map<string, number>();
  const prob = (pips: number, turn: number, k: number): number => {
    const key = `${pips}:${turn}:${k}`;
    let p = cache.get(key);
    if (p == null) {
      p = castOnCurveProbability(deckSize, lands, k, pips, turn);
      cache.set(key, p);
    }
    return p;
  };

  return (color, sources) => {
    const s = Math.max(0, Math.min(lands, sources));
    const lo = Math.floor(s);
    const frac = s - lo;
    let value = 0;
    for (const { pips, turn, weight } of grouped.get(color)?.values() ?? []) {
      const p = frac > 0
        ? prob(pips, turn, lo) * (1 - frac) + prob(pips, turn, Math.min(lands, lo + 1)) * frac
        : prob(pips, turn, lo);
      value += weight * p;
    }
    return value / totalWeight;
  };
}

function emptyColorRecord(): Record<MtgColor, number> {
  return { W: 0, U: 0, B: 0, R: 0, G: 0 };
}

/** Effective sources from non-land producers (0.5 per colour produced). */
function producerSources(spells: SpellInfo[], colors: MtgColor[]): Record<MtgColor, number> {
  const result = emptyColorRecord();
  for (const spell of spells) {
    const produced = (spell.producedMana ?? []).filter(isColor);
    if (!spell.isManaProducer || produced.length === 0) {
      continue;
    }
    for (const color of colors) {
      if (produced.includes(color)) {
        result[color] += 0.5 * spell.quantity;
      }
    }
  }
  return result;
}

function landSources(lands: { profile: LandProfile; quantity: number }[]): Record<MtgColor, number> {
  const result = emptyColorRecord();
  for (const { profile, quantity } of lands) {
    for (const color of profile.colors) {
      result[color] += quantity;
    }
  }
  return result;
}

function basicOption(color: MtgColor): LandOption {
  return {
    land: {
      title: BASIC_FOR_COLOR[color],
      typeLine: `Basic Land — ${BASIC_FOR_COLOR[color]}`,
      oracleText: `({T}: Add {${color}}.)`,
      producedMana: [color],
    },
    cardId: null,
    available: Infinity,
    free: Infinity,
    owned: Infinity,
    usedIn: [],
    price: null,
  };
}

/** Builds a land base proposal. */
export function planLandBase(input: LandBaseInput): LandBasePlan {
  const colors = ALL_COLORS.filter(c => input.deckColors.includes(c));
  const spells = input.spells;
  const castable = input.commander != null ? [...spells, input.commander] : spells;

  // Land count.
  const spellCount = spells.reduce((s, c) => s + c.quantity, 0);
  const avgCmc = spellCount > 0 ? spells.reduce((s, c) => s + c.cmc * c.quantity, 0) / spellCount : 0;
  const cheapRampDraw = spells.reduce((s, c) => s + (isCheapRampOrDraw(c) ? c.quantity : 0), 0);
  const formula = recommendedLandCount(avgCmc, cheapRampDraw, input.deckSize);
  const landCount = input.landCountOverride != null && input.landCountOverride > 0
    ? Math.round(input.landCountOverride)
    : formula.count;

  // Colour targets.
  const producers = producerSources(spells, colors);
  const reqs = requirements(castable, colors);
  const neededCache = new Map<string, { sources: number; unreachable: boolean }>();
  const targets = new Map<MtgColor, { target: number; driver: Requirement | null; unreachable: boolean }>();
  for (const color of colors) {
    targets.set(color, { target: 0, driver: null, unreachable: false });
  }
  for (const req of reqs) {
    const key = `${req.pips}:${req.turn}`;
    let needed = neededCache.get(key);
    if (needed == null) {
      needed = sourcesNeeded(input.deckSize, landCount, req.pips, req.turn);
      neededCache.set(key, needed);
    }
    const current = targets.get(req.color)!;
    const better = needed.sources > current.target
      || (needed.sources === current.target && current.driver != null && req.turn < current.driver.turn);
    if (better) {
      targets.set(req.color, { target: needed.sources, driver: req, unreachable: needed.unreachable });
    }
  }

  // Pip share, for spending surplus slots.
  const pipTotals = emptyColorRecord();
  for (const req of reqs) {
    pipTotals[req.color] += req.pips;
  }
  const pipSum = colors.reduce((s, c) => s + pipTotals[c], 0);
  const share = (c: MtgColor): number => (pipSum > 0 ? pipTotals[c] / pipSum : 1 / Math.max(1, colors.length));

  // Utility lands already in the deck stay.
  const currentProfiled = input.currentLands.map(cl => ({
    ...cl,
    profile: landProfile(cl.land, colors, input.commanderFormat),
  }));
  const picks = new Map<string, LandPick>();
  let slots = landCount;
  for (const cl of currentProfiled) {
    if (cl.profile.kind !== 'utility' || slots <= 0) {
      continue;
    }
    const quantity = Math.min(cl.quantity, slots);
    const option = input.options.find(o => o.land.title === cl.land.title);
    picks.set(cl.land.title, {
      option: option ?? {
        land: cl.land,
        cardId: null,
        available: quantity,
        free: quantity,
        owned: quantity,
        usedIn: [],
        price: null,
      },
      profile: cl.profile,
      quantity,
      missing: 0,
      kept: true,
    });
    slots -= quantity;
  }

  // Greedy fill.
  const candidates = [
    ...colors.map(basicOption),
    ...input.options.filter(o => !/\bbasic\b/i.test(o.land.typeLine)),
  ].map(option => ({ option, profile: landProfile(option.land, colors, input.commanderFormat) }))
    .filter(c => c.profile.colors.length > 0);

  // The value of a land is how many more coloured spells it makes castable
  // on curve (summed over every spell, not just the hardest one). This has
  // diminishing returns built in, so one unreachable BBBB spell cannot starve
  // the other colours.
  const castValue = castableValue(input.deckSize, landCount, reqs, colors);
  const sources = { ...producers };
  let tappedPicked = 0;
  for (let i = 0; i < slots; i++) {
    const marginal = emptyColorRecord();
    for (const color of colors) {
      marginal[color] = castValue(color, sources[color] + 1) - castValue(color, sources[color])
        + SURPLUS_WEIGHT * share(color);
    }
    let best: { option: LandOption; profile: LandProfile; score: number } | null = null;
    for (const cand of candidates) {
      const used = picks.get(cand.option.land.title)?.quantity ?? 0;
      const isBasic = cand.profile.kind === 'basic';
      const limit = isBasic ? cand.option.available : Math.min(cand.option.available, input.maxCopies);
      if (used >= limit) {
        continue;
      }
      const gain = cand.profile.colors.reduce((s, c) => s + marginal[c], 0);
      let score = gain * SPEED_FACTOR[cand.profile.speed];
      if (cand.profile.speed === 'tapped') {
        score *= TAPPED_DECAY ** tappedPicked;
      }
      if (cand.profile.painful) {
        score *= PAIN_FACTOR;
      }
      if (cand.profile.costed) {
        score *= COSTED_FACTOR;
      }
      // Only meaningful in cardbase mode: from the collection everything is
      // owned, and basics should still win ties there.
      if (!isBasic && cand.option.available === Infinity && cand.option.free > used) {
        score *= OWNED_BONUS;
      }
      if (best == null || compareCandidates(score, cand, best) < 0) {
        best = { ...cand, score };
      }
    }
    if (best == null) {
      break;
    }
    const existing = picks.get(best.option.land.title);
    picks.set(best.option.land.title, {
      option: best.option,
      profile: best.profile,
      quantity: (existing?.quantity ?? 0) + 1,
      missing: 0,
      kept: false,
    });
    for (const color of best.profile.colors) {
      sources[color] += 1;
    }
    if (best.profile.speed === 'tapped') {
      tappedPicked += 1;
    }
  }

  for (const pick of picks.values()) {
    pick.missing = pick.profile.kind === 'basic' || pick.kept
      ? 0
      : Math.max(0, pick.quantity - pick.option.free);
  }

  // Before and after.
  const currentLandCount = input.currentLands.reduce((s, l) => s + l.quantity, 0);
  const currentSources = landSources(currentProfiled);
  const proposedSources = landSources([...picks.values()]);
  const proposedLandCount = [...picks.values()].reduce((s, p) => s + p.quantity, 0);
  const currentValue = castableValue(input.deckSize, currentLandCount, reqs, colors);
  const castableCurrent = colors.reduce((s, c) => s + currentValue(c, currentSources[c] + producers[c]), 0);
  const castableProposed = colors.reduce((s, c) => s + castValue(c, proposedSources[c] + producers[c]), 0);
  const colorTargets: ColorTarget[] = colors.map(color => {
    const t = targets.get(color)!;
    const current = currentSources[color] + producers[color];
    const proposed = proposedSources[color] + producers[color];
    const prob = (lands: number, src: number): number => (t.driver == null
      ? 1
      : castOnCurveProbability(input.deckSize, lands, src, t.driver.pips, t.driver.turn));
    return {
      color,
      target: t.target,
      driver: t.driver != null ? { title: t.driver.title, pips: t.driver.pips, turn: t.driver.turn } : null,
      unreachable: t.unreachable,
      fromProducers: producers[color],
      current,
      proposed,
      probCurrent: prob(currentLandCount, current),
      probProposed: prob(proposedLandCount, proposed),
    };
  });

  // Changes compared with the current lands.
  const currentByTitle = new Map<string, number>();
  for (const cl of input.currentLands) {
    currentByTitle.set(cl.land.title, (currentByTitle.get(cl.land.title) ?? 0) + cl.quantity);
  }
  const add: { title: string; quantity: number }[] = [];
  const remove: { title: string; quantity: number }[] = [];
  for (const pick of picks.values()) {
    const diff = pick.quantity - (currentByTitle.get(pick.option.land.title) ?? 0);
    if (diff > 0) {
      add.push({ title: pick.option.land.title, quantity: diff });
    }
  }
  for (const [title, quantity] of currentByTitle) {
    const diff = quantity - (picks.get(title)?.quantity ?? 0);
    if (diff > 0) {
      remove.push({ title, quantity: diff });
    }
  }

  const kindOrder: LandKind[] = ['utility', 'rainbow', 'tri', 'dual', 'fetch', 'mono', 'basic'];
  const sortedPicks = [...picks.values()].sort((a, b) =>
    kindOrder.indexOf(a.profile.kind) - kindOrder.indexOf(b.profile.kind)
    || a.option.land.title.localeCompare(b.option.land.title));

  return {
    landCount,
    landCountFormula: formula.formula,
    avgCmc,
    cheapRampDraw,
    currentLandCount,
    castableCurrent: reqs.length > 0 ? castableCurrent : 1,
    castableProposed: reqs.length > 0 ? castableProposed : 1,
    targets: colorTargets,
    picks: sortedPicks,
    add: add.sort((a, b) => a.title.localeCompare(b.title)),
    remove: remove.sort((a, b) => a.title.localeCompare(b.title)),
  };
}

/** Negative when `cand` should be picked over `best`. */
function compareCandidates(
  score: number,
  cand: { option: LandOption; profile: LandProfile },
  best: { option: LandOption; profile: LandProfile; score: number },
): number {
  if (Math.abs(score - best.score) > 1e-9) {
    return best.score - score;
  }
  const candBasic = cand.profile.kind === 'basic' ? 0 : 1;
  const bestBasic = best.profile.kind === 'basic' ? 0 : 1;
  if (candBasic !== bestBasic) {
    return candBasic - bestBasic;
  }
  const candPrice = cand.option.price ?? Infinity;
  const bestPrice = best.option.price ?? Infinity;
  if (candPrice !== bestPrice) {
    return candPrice - bestPrice;
  }
  return cand.option.land.title.localeCompare(best.option.land.title);
}
