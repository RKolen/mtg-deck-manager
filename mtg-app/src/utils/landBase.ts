/**
 * Land base suggestion.
 *
 * Pure functions: given a deck's spells, its current lands and a pool of
 * candidate lands, propose a land base. No AI and no network.
 *
 * 1. Land count: Frank Karsten's regression on average mana value and cheap
 *    ramp/draw (99-card and 60-card versions, scaled for other sizes).
 * 2. Source target per colour: the fewest sources so that the most
 *    demanding spell of that colour is castable on curve, given that the
 *    land drops were hit. Karsten's 2022 model: on the play, a goal of
 *    89% + mana value (up to 96%), London mulligans, and in Commander a free
 *    mulligan and an extra draw. Exact, not simulated; within one source of
 *    all 76 values in his table (40, 60, 80 and 99 cards).
 * 3. Non-land mana producers count 0.5 source per colour, as elsewhere in the
 *    app; the lands cover the rest.
 * 4. Lands are picked one at a time. While any colour is short of its
 *    target, the largest relative shortfall goes first, so a shortfall that
 *    cannot be closed is shared in proportion to the targets; duals count
 *    double only when the slots left cannot close every shortfall one colour
 *    at a time. Once all targets are met, lands are picked by how many more
 *    spells they make castable, weighted by how fast they enter. Basics are
 *    unlimited and win ties.
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
  /** Scryfall rarity; mythic MDFCs count more (Karsten). */
  rarity?: string;
}

export type LandSpeed = 'untapped' | 'conditional' | 'tapped';

export type LandKind = 'basic' | 'fetch' | 'rainbow' | 'tri' | 'dual' | 'mono' | 'utility';

export interface LandProfile {
  /**
   * Deck colours this land can make. For a fetch: the colours of the basic
   * types it names; what it really finds depends on the deck's lands.
   */
  colors: MtgColor[];
  speed: LandSpeed;
  kind: LandKind;
  /** Costs life every time it taps for coloured mana. */
  painful: boolean;
  /** Life lost per coloured tap (1 for painlands, 3 for Tarnished Citadel). */
  painDamage: number;
  /** Hurts on every tap, colourless included (City of Brass, Mana Confluence). */
  painEveryTap: boolean;
  /** Pays life to enter untapped (shocklands). */
  shock: boolean;
  /** Land // Land (Pathways): you pick one face when playing it. */
  modal: boolean;
  /**
   * Does something besides making mana: surveil or scry on entering,
   * cycling, turning into a creature, or another ability (Karakas).
   */
  upside: boolean;
  /**
   * Costs something on every coloured tap: life (City of Brass, Mana
   * Confluence) or a gift to the opponent (Forbidden Orchard).
   */
  drawback: boolean;
  /**
   * A drawback too big for a normal source: 2+ damage per tap (Tarnished
   * Citadel), or returning to hand so it eats the land drop every turn
   * (Undiscovered Paradise).
   */
  heavyDrawback: boolean;
  /** Coloured mana needs extra mana (filter lands). */
  costed: boolean;
  /** Can make its colours untapped on turn one (fastlands yes, checklands no). */
  turnOne: boolean;
  /** Share of a tapped land it counts as against the tapped limit. */
  tappedWeight: number;
  /** Basic land types on the type line, lower case ('swamp', 'mountain'). */
  basicTypes: string[];
  /** What a fetch can find, or null for other lands. */
  fetch: { types: string[]; basicOnly: boolean } | null;
}

/** How much a non-land mana card counts. */
export interface ProducerRatio {
  /** Land equivalents in the land count formula (cheap cards only). */
  land: number;
  /** Sources of each colour it makes. */
  source: number;
  /** Counts only for spells of this mana value or more. */
  minMv: number;
}

/**
 * Per-deck ratios, Karsten's values by default. Mana dorks, rocks and ramp
 * spells count as part of a source, and only for spells they can speed up.
 */
export interface ManaSettings {
  dork: ProducerRatio;
  rock: ProducerRatio;
  /** Spells costing 2 or less that put a land onto the battlefield. */
  ramp2: ProducerRatio;
  /** Spells costing 3 that put a land onto the battlefield. */
  ramp3: ProducerRatio;
  /** Cheap cards that make a Treasure. */
  treasure: ProducerRatio;
  /** Modal double-faced spell // land, not mythic. */
  mdfc: ProducerRatio;
  mdfcMythic: ProducerRatio;
  /** A fetch with fewer targets of a colour than the spell's pips. */
  fetchPartial: number;
  /**
   * Fetches give at most this many sources of a colour per fetchable land of
   * that colour; beyond that each one is worth less, since every fetch uses
   * up a target.
   */
  fetchesPerTarget: number;
  /**
   * Basics of each colour the land base keeps at least, so every colour can
   * still be cast under Blood Moon or Back to Basics, or after a Wasteland.
   * Karsten's model has no such need, so the default is none.
   */
  minBasics: Record<MtgColor, number>;
  /** Count restrictive sideboard spells' colour needs too (Karsten does). */
  includeSideboard: boolean;
  /** Per-card changes, keyed by card title. */
  cards: Record<string, CardOverride>;
  /**
   * Lands the plan always keeps (Karakas in a control deck): power the
   * planner cannot read from the card text.
   */
  keepLands: string[];
  /** The deck's chosen land count, or null for the formula. */
  landCount: number | null;
}

/**
 * How a card is really cast in this deck. Used for the colour targets, the
 * average mana value and the cheap spell count; not for charts or legality.
 */
export interface CardOverride {
  /** Realistic cost, e.g. "{G}" for a delve spell (Become Immense). */
  cost?: string | null;
  /** Turn it needs to be cast on, when that is later than its mana value. */
  turn?: number | null;
  /** Never cast from hand (a reanimation target): no colour need, not in the average. */
  ignore?: boolean;
  /**
   * Not needed on curve (a pump spell next to key creatures): it does not
   * set a colour target and counts as castable one turn later. Cards are
   * key by default, as in Karsten's model, except cards with an alternate
   * cost; false makes those key cards too.
   */
  canWait?: boolean | null;
}

export const DEFAULT_MANA_SETTINGS: ManaSettings = {
  dork: { land: 0.28, source: 0.5, minMv: 2 },
  rock: { land: 0.28, source: 0.75, minMv: 3 },
  ramp2: { land: 0.28, source: 0.75, minMv: 3 },
  ramp3: { land: 0.28, source: 0.5, minMv: 5 },
  treasure: { land: 0.28, source: 0.25, minMv: 3 },
  mdfc: { land: 0.4, source: 0.8, minMv: 2 },
  mdfcMythic: { land: 0.75, source: 1, minMv: 2 },
  fetchPartial: 0.8,
  fetchesPerTarget: 2,
  minBasics: { W: 0, U: 0, B: 0, R: 0, G: 0 },
  includeSideboard: false,
  cards: {},
  keepLands: [],
  landCount: null,
};

const PRODUCER_KINDS = ['dork', 'rock', 'ramp2', 'ramp3', 'treasure', 'mdfc', 'mdfcMythic'] as const;

type ProducerKind = typeof PRODUCER_KINDS[number];

/** Fills a deck's saved differences in with the defaults. */
export function resolveManaSettings(saved: Partial<ManaSettings> | null | undefined): ManaSettings {
  const result: ManaSettings = { ...DEFAULT_MANA_SETTINGS, cards: { ...(saved?.cards ?? {}) } };
  for (const key of PRODUCER_KINDS) {
    const value = saved?.[key];
    if (value != null && typeof value === 'object') {
      result[key] = { ...DEFAULT_MANA_SETTINGS[key], ...value };
    }
  }
  if (typeof saved?.fetchPartial === 'number') {
    result.fetchPartial = saved.fetchPartial;
  }
  if (typeof saved?.fetchesPerTarget === 'number' && saved.fetchesPerTarget > 0) {
    result.fetchesPerTarget = saved.fetchesPerTarget;
  }
  // A number means that many basics of each colour the deck plays.
  const minBasics: unknown = saved?.minBasics;
  result.minBasics = { ...DEFAULT_MANA_SETTINGS.minBasics };
  for (const color of ALL_COLORS) {
    const value = typeof minBasics === 'number'
      ? minBasics
      : minBasics != null && typeof minBasics === 'object' ? (minBasics as Record<string, unknown>)[color] : 0;
    if (typeof value === 'number' && value > 0) {
      result.minBasics[color] = Math.round(value);
    }
  }
  if (typeof saved?.includeSideboard === 'boolean') {
    result.includeSideboard = saved.includeSideboard;
  }
  if (Array.isArray(saved?.keepLands)) {
    result.keepLands = saved.keepLands.filter((t): t is string => typeof t === 'string' && t !== '');
  }
  if (typeof saved?.landCount === 'number' && saved.landCount > 0) {
    result.landCount = Math.round(saved.landCount);
  }
  return result;
}

/**
 * Reads a deck's stored mana settings. Anything that is not a JSON object
 * counts as no changes, so a bad value never breaks the panel.
 */
export function parseManaSettings(json: string | null | undefined): Partial<ManaSettings> {
  if (json == null || json.trim() === '') {
    return {};
  }
  try {
    const value: unknown = JSON.parse(json);
    return value != null && typeof value === 'object' && !Array.isArray(value) ? value as Partial<ManaSettings> : {};
  }
  catch {
    return {};
  }
}

/**
 * The differences from the defaults, for storing: unchanged ratios, empty
 * card overrides and default switches are left out. Returns null when
 * nothing differs.
 */
export function manaSettingsDiff(settings: Partial<ManaSettings>): Partial<ManaSettings> | null {
  const full = resolveManaSettings(settings);
  const diff: Partial<ManaSettings> = {};
  for (const key of PRODUCER_KINDS) {
    const changed: Partial<ProducerRatio> = {};
    for (const field of ['land', 'source', 'minMv'] as const) {
      if (full[key][field] !== DEFAULT_MANA_SETTINGS[key][field]) {
        changed[field] = full[key][field];
      }
    }
    if (Object.keys(changed).length > 0) {
      diff[key] = changed as ProducerRatio;
    }
  }
  if (full.fetchPartial !== DEFAULT_MANA_SETTINGS.fetchPartial) {
    diff.fetchPartial = full.fetchPartial;
  }
  if (full.fetchesPerTarget !== DEFAULT_MANA_SETTINGS.fetchesPerTarget) {
    diff.fetchesPerTarget = full.fetchesPerTarget;
  }
  const minBasics = Object.fromEntries(ALL_COLORS.filter(c => full.minBasics[c] > 0).map(c => [c, full.minBasics[c]]));
  if (Object.keys(minBasics).length > 0) {
    diff.minBasics = minBasics as Record<MtgColor, number>;
  }
  if (full.includeSideboard !== DEFAULT_MANA_SETTINGS.includeSideboard) {
    diff.includeSideboard = full.includeSideboard;
  }
  if (full.keepLands.length > 0) {
    diff.keepLands = [...new Set(full.keepLands)].sort((a, b) => a.localeCompare(b));
  }
  if (full.landCount != null) {
    diff.landCount = full.landCount;
  }
  const cards: Record<string, CardOverride> = {};
  for (const [title, override] of Object.entries(full.cards)) {
    const kept: CardOverride = {};
    if (override.cost != null && override.cost.trim() !== '') {
      kept.cost = override.cost.trim();
    }
    if (override.turn != null && override.turn > 0) {
      kept.turn = Math.round(override.turn);
    }
    if (override.ignore === true) {
      kept.ignore = true;
    }
    // False is kept too: it makes an alternate-cost card a key card again.
    if (override.canWait != null) {
      kept.canWait = override.canWait;
    }
    if (Object.keys(kept).length > 0) {
      cards[title] = kept;
    }
  }
  if (Object.keys(cards).length > 0) {
    diff.cards = cards;
  }
  return Object.keys(diff).length > 0 ? diff : null;
}

/** Mana value of a cost string: {2}{G}{G} = 4, {X} = 0, {2/W} = 2. */
export function manaValueOf(cost: string): number {
  let total = 0;
  for (const [, symbol] of cost.matchAll(/\{([^}]+)\}/g)) {
    const s = symbol!.toUpperCase();
    if (/^\d+$/.test(s)) {
      total += Number(s);
    }
    else if (/^2\//.test(s)) {
      total += 2;
    }
    else if (!/^[XYZ]$/.test(s)) {
      total += 1;
    }
  }
  return total;
}

/** Keywords that let a spell be cast for less than its mana value. */
const ALTERNATE_COSTS: [string, RegExp][] = [
  ['delve', /\bdelve\b/],
  ['convoke', /\bconvoke\b/],
  ['affinity', /\baffinity for\b/],
  ['improvise', /\bimprovise\b/],
  ['emerge', /\bemerge\b/],
  ['evoke', /\bevoke\b/],
  ['overload', /\boverload\b/],
  ['spectacle', /\bspectacle\b/],
  ['dash', /\bdash\b/],
  ['prowl', /\bprowl\b/],
  ['surge', /\bsurge\b/],
  ['miracle', /\bmiracle\b/],
  ['cycling', /\bcycling\b/],
  ['domain', /\bdomain\b[^\n]*costs? \{1\} less/],
  ['costs less', /\bthis spell costs \{\d+\} less\b/],
  // Force of Will, Snuff Out. "Cast ... without paying" is about other
  // cards (Prey's Vengeance) and is not matched.
  ['alternative cost', /rather than pay this spell's mana cost/],
];

/** Why a card may cost less than its mana value, or '' when it cannot. */
export function alternateCostReason(spell: { oracleText: string; manaCost: string }): string {
  const text = spell.oracleText.toLowerCase();
  const reasons = ALTERNATE_COSTS.filter(([, re]) => re.test(text)).map(([name]) => name);
  if (/\{x\}/i.test(spell.manaCost.split(' // ')[0] ?? '')) {
    reasons.push('X spell');
  }
  return reasons.join(', ');
}

/**
 * Cards whose real cost may differ from their mana value: alternate cost
 * keywords and X spells. Cards with a cost, turn or can-wait setting are
 * left out; until then they count as able to wait.
 */
export function alternateCostCards(
  spells: SpellInfo[],
  settings: Partial<ManaSettings> | null = null,
): { title: string; reason: string }[] {
  const overrides = settings?.cards ?? {};
  const result: { title: string; reason: string }[] = [];
  for (const spell of spells) {
    if (isDecided(overrides[spell.title])) {
      continue;
    }
    const reason = alternateCostReason(spell);
    if (reason !== '') {
      result.push({ title: spell.title, reason });
    }
  }
  return result;
}

/** True when an override says how the card is cast (not just an empty row). */
function isDecided(override: CardOverride | undefined): boolean {
  return override != null && (
    (override.cost != null && override.cost.trim() !== '')
    || (override.turn != null && override.turn > 0)
    || override.canWait != null
    || override.ignore === true
  );
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
  /** The deck's ratio changes; missing values use DEFAULT_MANA_SETTINGS. */
  settings?: Partial<ManaSettings> | null;
  /** Non-land sideboard cards, used when settings.includeSideboard is on. */
  sideboard?: SpellInfo[];
  /**
   * Build the land base from scratch even though the deck has lands. By
   * default a deck with lands keeps them and only gets swaps that clearly
   * close a colour shortfall.
   */
  rebuild?: boolean;
}

export interface ColorTarget {
  color: MtgColor;
  /** Effective sources wanted (lands plus 0.5 per non-land producer). */
  target: number;
  /** The spell that sets the target. */
  driver: { title: string; pips: number; turn: number } | null;
  /** Chance the driver should be castable on curve (0.90-0.96). */
  goal: number;
  /** True when even all lands making this colour would not reach the goal. */
  unreachable: boolean;
  fromProducers: number;
  current: number;
  proposed: number;
  /** P(casting the driver on curve) with the current and proposed lands. */
  probCurrent: number;
  probProposed: number;
  /**
   * Sources that make the colour untapped on turn one, for one-drops, or
   * null when the deck has no one-drop of this colour.
   */
  turnOne: { target: number; unreachable: boolean; current: number; proposed: number } | null;
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

export interface UnionTarget {
  colors: MtgColor[];
  driver: { title: string; pips: number; turn: number };
  target: number;
  unreachable: boolean;
  current: number;
  proposed: number;
}

export interface LandBasePlan {
  landCount: number;
  landCountFormula: string;
  /** What the formula alone suggests (MDFCs taken off), shown as advice. */
  formulaLandCount: number;
  avgCmc: number;
  cheapRampDraw: number;
  currentLandCount: number;
  /** Land equivalents from spell // land cards (MDFCs), counted in landCount. */
  mdfcLands: number;
  /** Most tapped lands for this deck size (conditional lands count 1/4). */
  tappedLimit: number;
  tappedCurrent: number;
  tappedProposed: number;
  /**
   * Chance that a fetch drawn by then finds nothing left to fetch, with the
   * proposed lands, or empty without fetches.
   */
  deadFetch: { turn: number; chance: number }[];
  /**
   * Gold and hybrid spells: lands making any of these colours (Karsten's
   * union requirement), e.g. 21 lands making B or R for {B}{R} on turn 2.
   */
  unionTargets: UnionTarget[];
  /** Cards that may be cast for less than their mana value, without an override. */
  alternateCosts: { title: string; reason: string }[];
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

/**
 * Required chance to cast a spell on curve: Karsten's 89% + mana value,
 * so 90% for one-drops up to 96% for seven-drops and above.
 */
export function castGoal(turn: number): number {
  return (89 + Math.min(7, Math.max(1, Math.round(turn)))) / 100;
}

/**
 * London mulligan stages. A hand is kept when its land count after putting
 * cards on the bottom is within the range; the last stage always keeps.
 * Karsten mulligans 0, 1, 6 and 7 landers on seven, 0, 1, 5 and 6 on six,
 * 0, 1 and 5 on five, and keeps any four. Commander's free mulligan also
 * sends back two-landers.
 */
interface MulliganStage {
  size: number;
  minLands: number;
  maxLands: number;
}

const MULLIGAN_STAGES: MulliganStage[] = [
  { size: 7, minLands: 2, maxLands: 5 },
  { size: 6, minLands: 2, maxLands: 4 },
  { size: 5, minLands: 2, maxLands: 4 },
  { size: 4, minLands: 0, maxLands: 7 },
];

const FREE_MULLIGAN: MulliganStage = { size: 7, minLands: 3, maxLands: 5 };

/** Results of castOnCurveProbability, which the fill asks for many times. */
const probabilityCache = new Map<string, number>();
const PROBABILITY_CACHE_LIMIT = 50000;

export const BASIC_FOR_COLOR: Record<MtgColor, string> = {
  W: 'Plains',
  U: 'Island',
  B: 'Swamp',
  R: 'Mountain',
  G: 'Forest',
};

const BASIC_TYPES = ['plains', 'island', 'swamp', 'mountain', 'forest'];

/** Karsten counts a conditional land as a quarter of a tapped land. */
const TAPPED_WEIGHT: Record<LandSpeed, number> = {
  untapped: 0,
  conditional: 0.25,
  tapped: 1,
};

/**
 * Most tapped lands in a 60-card deck: Karsten's midrange limit. His
 * aggro limit is 3, but the deck's archetype is not known here. Scaled by
 * deck size (99 cards: 15).
 */
const TAPPED_LIMIT_60 = 9;

/** Karsten's land count formula counts a cheap ramp or draw spell as 0.28 lands. */
const CHEAP_LAND_EQUIVALENT = 0.28;

/** Turns the dead-fetch chance is shown for. */
const DEAD_FETCH_TURNS = [4, 8];

const SPEED_FACTOR: Record<LandSpeed, number> = {
  untapped: 1,
  conditional: 0.85,
  tapped: 0.6,
};

/**
 * Speed factor while a colour target is still short. Karsten counts tapped
 * lands as full sources, so this only breaks ties: a tapped dual beats a
 * basic while it closes two shortfalls, and loses once it closes one.
 */
const SHORTFALL_SPEED_FACTOR: Record<LandSpeed, number> = {
  untapped: 1,
  conditional: 0.9,
  tapped: 0.75,
};

/**
 * While targets are short but reachable one colour per land, the share a
 * land's other colours add: enough for an untapped dual to beat a basic, not
 * for a tapped dual to.
 */
const EXTRA_COLOUR_WEIGHT = 0.25;

/** Copies looked ahead once targets are met (CCC spells need three sources). */
const LOOKAHEAD_COPIES = 3;

/** Each tapped land picked makes the next one less attractive. */
const TAPPED_DECAY = 0.9;

/** Painlands, City of Brass, Mana Confluence: slightly worse than a clean source. */
const PAIN_FACTOR = 0.92;

/** City of Brass, Mana Confluence: they hurt on every tap. */
const PAIN_EVERY_TAP_FACTOR = 0.7;

/** In a deck with fetches, lands the fetches can find are worth more. */
const FETCHABLE_BONUS = 1.25;

/**
 * Two or more damage per coloured tap (Tarnished Citadel deals 3): a last
 * resort, like filter lands, even when it fixes every colour.
 */
const HEAVY_PAIN_DAMAGE = 2;
const HEAVY_PAIN_FACTOR = 0.3;

/** Each land with a drawback on every tap makes the next one less attractive. */
const DRAWBACK_DECAY = 0.85;

/** Filter lands ({1}, {T}: Add any colour): a last resort for fixing. */
const COSTED_FACTOR = 0.3;

/** A filter land counts as half a source of each colour it filters into. */
const COSTED_SOURCE = 0.5;

/** Shocklands pay 2 life to enter untapped; real duals win the tie. */
const SHOCK_FACTOR = 0.97;

/**
 * Least share of a colour target a swap must close to be suggested, so a
 * tested land base is not churned for rounding-level gains.
 */
const MIN_SWAP_GAIN = 0.05;

/** Share of a target (at least one source) a deck may be short without swaps. */
const SWAP_TOLERANCE = 0.1;

/** Least rise in the share of castable spells a swap must bring (1 point). */
const MIN_CASTABLE_GAIN = 0.01;

/** Removing a non-basic the deck chose needs this many times the evidence. */
const NONBASIC_REMOVAL_EVIDENCE = 2;

/** Non-basic lands already in the deck win near ties. */
const CURRENT_BONUS = 1.3;

/** Lands that do something besides making mana (surveil, cycling, manlands). */
const UPSIDE_BONUS = 1.1;

/**
 * With domain cards (Leyline Binding), each basic land type a land adds
 * that the land base does not have yet (Xander's Lounge adds Swamp and
 * Mountain to Bant).
 */
const DOMAIN_TYPE_BONUS = 0.35;

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
    // Verges: "{T}: Add {U}. Activate only if you control an Island or a
    // Mountain." The second colour works once you have that land, like a
    // checkland's, so it is a real source rather than a restricted one.
    const effect = line.slice(colon + 1).replace(/ activate only if you control an? \w+ or an? \w+\.?$/, '');
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

/**
 * Whether a land does something besides making mana: surveil or scry on
 * entering, cycling, becoming a creature, or an ability that does not add
 * mana (Karakas, Academy Ruins).
 */
function hasUpside(text: string): boolean {
  if (/\b(?:surveil|scry|cycling)\b|becomes? an? [^.]*creature/.test(text)) {
    return true;
  }
  return text.split('\n').some(rawLine => {
    const line = rawLine.replace(/\([^)]*\)/g, '').trim();
    const colon = line.indexOf(':');
    return colon > 0 && /\{t\}|\{\d\}/.test(line.slice(0, colon)) && !/\badd\b|search your library/.test(line.slice(colon));
  });
}

/** Classifies a land for a deck playing the given colours. */
export function landProfile(land: LandInfo, deckColors: MtgColor[], commanderFormat: boolean): LandProfile {
  const text = land.oracleText.toLowerCase();
  const isBasic = /\bbasic\b/i.test(land.typeLine);
  const entersTapped = /(?:this land|it) enters (?:the battlefield )?tapped\./.test(text)
    || /^this land enters tapped\.?$/m.test(text);
  const frontType = (land.typeLine.split(' // ')[0] ?? '').toLowerCase();
  const subtypes = frontType.split(/\s+[—-]\s+/)[1] ?? '';
  const basicTypes = BASIC_TYPES.filter(t => new RegExp(`\\b${t}\\b`).test(subtypes));

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
    const basicOnly = /basic land card/.test(ability);
    const types = basicOnly ? [...BASIC_TYPES] : BASIC_TYPES.filter(t => ability.includes(t));
    return {
      colors: fetched,
      speed,
      kind: types.length > 0 ? 'fetch' : 'utility',
      painful: false,
      painDamage: 0,
      painEveryTap: false,
      shock: false,
      modal: false,
      upside: false,
      drawback: false,
      heavyDrawback: false,
      costed: false,
      turnOne: speed === 'untapped',
      tappedWeight: TAPPED_WEIGHT[speed],
      basicTypes,
      fetch: types.length > 0 ? { types, basicOnly } : null,
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
  // Pathways (Land // Land): only the front face's text is stored, so the
  // back face's colour comes from produced mana. You pick a face, but
  // Karsten counts a Pathway as a full source of both colours.
  const faces = land.typeLine.split(' // ');
  if (faces.length > 1 && faces.every(face => /\bland\b/i.test(face))) {
    colors = deckColors.filter(c => colors.includes(c) || (land.producedMana ?? []).includes(c));
  }
  let costed = false;
  if (colors.length === 0) {
    colors = colorsOf(abilities);
    costed = colors.length > 0;
  }
  const anyColor = abilities.some(a => !a.costed && a.colors === 'any');
  const painDamage = Math.max(
    0,
    ...[...text.matchAll(/deals (\d+) damage to you|pay (\d+) life:/g)].map(m => Number(m[1] ?? m[2])),
  );
  const painful = painDamage > 0;
  // City of Brass and Mana Confluence hurt on every tap; a painland can tap
  // for colourless without damage.
  const painEveryTap = painful && (/whenever this land becomes tapped/.test(text) || !/^\{t\}: add \{c\}\.?$/m.test(text));

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

  // Conditional lands that are untapped on turn one: fastlands, Forbidden
  // Orchard, Undiscovered Paradise. Checklands, slowlands, Exotic Orchard
  // and Lairs are not.
  const turnOne = speed === 'untapped' || (speed === 'conditional' && (
    /two or fewer other lands/.test(text)
    || /target opponent creates/.test(text)
    || /return this land to its owner's hand/.test(text)
  ));

  return {
    colors,
    speed,
    kind,
    painful,
    painDamage,
    painEveryTap,
    shock: /pay \d+ life\. if you don'?t, it enters (?:the battlefield )?tapped/.test(text),
    modal: faces.length > 1 && faces.every(face => /\bland\b/i.test(face)),
    upside: hasUpside(text),
    drawback: painful || /target opponent creates|return this land to its owner's hand/.test(text),
    heavyDrawback: painDamage >= HEAVY_PAIN_DAMAGE || /return this land to its owner's hand/.test(text),
    costed,
    turnOne,
    tappedWeight: TAPPED_WEIGHT[speed],
    basicTypes,
    fetch: null,
  };
}

// ---------------------------------------------------------------------------
// Probability
// ---------------------------------------------------------------------------

/**
 * P(at least `pips` sources of a colour by `turn`, given at least `turn`
 * lands by then), on the play, after mulligans.
 *
 * Every opening seven is weighed exactly (hypergeometric). Mulligans follow
 * MULLIGAN_STAGES; on a mulligan to n, spells go to the bottom first down to
 * three lands kept, then lands that do not make the colour. Bottomed cards
 * cannot be drawn in the turns that matter.
 *
 * @param deckSize - Library size (60, 99, ...).
 * @param lands - Lands in the deck.
 * @param sources - Lands that make the colour (capped at `lands`).
 * @param pips - Coloured pips of the spell.
 * @param turn - Turn the spell should be cast (its mana value, 1-7).
 * @param commanderFormat - Free first mulligan and an extra draw (Commander).
 */
export function castOnCurveProbability(
  deckSize: number,
  lands: number,
  sources: number,
  pips: number,
  turn: number,
  commanderFormat = false,
): number {
  const N = Math.max(8, Math.round(deckSize));
  const L = Math.max(0, Math.min(N, Math.round(lands)));
  const K = Math.max(0, Math.min(L, Math.round(sources)));
  const key = `${N}:${L}:${K}:${pips}:${turn}:${commanderFormat ? 1 : 0}`;
  const cached = probabilityCache.get(key);
  if (cached != null) {
    return cached;
  }

  const offColour = L - K;
  const spells = N - L;
  const draws = Math.min(N - 7, turn - 1 + (commanderFormat ? 1 : 0));
  const library = N - 7;
  const handTotal = logBinomial(N, 7);
  const drawTotal = logBinomial(library, draws);

  // Chance of the land drop (hit) and of the spell being castable (ok) after
  // the draws, for a hand that looked at s sources and o other lands and kept
  // keptS and keptO of them.
  const outcome = (s: number, o: number, keptS: number, keptO: number): [number, number] => {
    let hit = 0;
    let ok = 0;
    const restSpells = library - (K - s) - (offColour - o);
    for (let a = 0; a <= Math.min(K - s, draws); a++) {
      for (let b = 0; b <= Math.min(offColour - o, draws - a); b++) {
        if (keptS + a + keptO + b < turn) {
          continue;
        }
        const q = Math.exp(
          logBinomial(K - s, a) + logBinomial(offColour - o, b) + logBinomial(restSpells, draws - a - b) - drawTotal,
        );
        hit += q;
        if (keptS + a >= pips) {
          ok += q;
        }
      }
    }
    return [hit, ok];
  };

  // Opening sevens: [sources, other lands, probability].
  const hands: [number, number, number][] = [];
  for (let s = 0; s <= Math.min(K, 7); s++) {
    for (let o = 0; o <= Math.min(offColour, 7 - s); o++) {
      const p = Math.exp(logBinomial(K, s) + logBinomial(offColour, o) + logBinomial(spells, 7 - s - o) - handTotal);
      if (p > 0) {
        hands.push([s, o, p]);
      }
    }
  }

  const stages = commanderFormat ? [FREE_MULLIGAN, ...MULLIGAN_STAGES] : MULLIGAN_STAGES;
  let reach = 1;
  let hitTotal = 0;
  let okTotal = 0;
  stages.forEach((stage, index) => {
    const last = index === stages.length - 1;
    const toBottom = 7 - stage.size;
    let mulligan = 0;
    for (const [s, o, p] of hands) {
      const spellCount = 7 - s - o;
      const spellsBottomed = Math.max(0, Math.min(toBottom, spellCount - Math.max(0, stage.size - 3)));
      const landsBottomed = Math.min(s + o, toBottom - spellsBottomed);
      const offBottomed = Math.min(o, landsBottomed);
      const keptS = s - (landsBottomed - offBottomed);
      const keptO = o - offBottomed;
      const kept = keptS + keptO;
      if (!last && (kept < stage.minLands || kept > stage.maxLands)) {
        mulligan += p;
        continue;
      }
      const [hit, ok] = outcome(s, o, keptS, keptO);
      hitTotal += reach * p * hit;
      okTotal += reach * p * ok;
    }
    reach *= mulligan;
  });

  const result = hitTotal > 0 ? okTotal / hitTotal : 0;
  if (probabilityCache.size >= PROBABILITY_CACHE_LIMIT) {
    probabilityCache.clear();
  }
  probabilityCache.set(key, result);
  return result;
}

/**
 * Fewest sources reaching castGoal(turn), or `lands` with `unreachable` set
 * when no count does.
 */
export function sourcesNeeded(
  deckSize: number,
  lands: number,
  pips: number,
  turn: number,
  commanderFormat = false,
): { sources: number; unreachable: boolean } {
  const goal = castGoal(turn);
  for (let k = pips; k <= lands; k++) {
    if (castOnCurveProbability(deckSize, lands, k, pips, turn, commanderFormat) >= goal) {
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

/** A colour need: lands making any colour in `colors`. */
interface Requirement {
  /** One colour, or several for gold and hybrid spells (union). */
  colors: MtgColor[];
  title: string;
  pips: number;
  turn: number;
  /** Sources added to the table value (Karsten: +1 per colour of a gold spell). */
  extra: number;
  /** False for cards that can wait: they count, but set no target. */
  drivesTarget: boolean;
  /** Copies of the spell. */
  weight: number;
}

/** A spell as it is really cast: override cost and turn applied. */
interface CastSpell extends SpellInfo {
  turn: number;
  canWait: boolean;
}

/** Applies the deck's card overrides; ignored cards are dropped. */
function castSpells(spells: SpellInfo[], settings: ManaSettings): CastSpell[] {
  const result: CastSpell[] = [];
  for (const spell of spells) {
    const override = settings.cards[spell.title];
    if (override?.ignore === true) {
      continue;
    }
    const cost = override?.cost != null ? override.cost : spell.manaCost;
    const cmc = override?.cost != null ? manaValueOf(override.cost) : spell.cmc;
    const turn = override?.turn != null && override.turn > 0 ? override.turn : cmc;
    // A card with an alternate cost (miracle, X, Force of Will) is rarely
    // cast on curve at its printed cost, so it can wait until the deck says
    // how it is really cast.
    const canWait = override?.canWait ?? (!isDecided(override) && alternateCostReason(spell) !== '');
    // A card that can wait counts as cast one turn later.
    result.push({
      ...spell,
      manaCost: cost,
      cmc,
      turn: Math.min(7, Math.max(1, Math.round(turn) + (canWait ? 1 : 0))),
      canWait,
    });
  }
  return result;
}

const setKey = (colors: MtgColor[]): string => colors.join('');

/**
 * Colour needs of each spell (Karsten 2022):
 * - each colour with plain pips needs the table's sources for those pips,
 *   one more for a gold spell;
 * - a gold or hybrid spell also needs lands making any of its colours for
 *   all its coloured pips together (hybrid pips count either colour).
 * Phyrexian and {2/C} pips are free and ignored.
 */
function requirements(spells: CastSpell[], colors: MtgColor[]): Requirement[] {
  const result: Requirement[] = [];
  for (const spell of spells) {
    // Split, adventure and double-faced cards list each face's cost; the
    // mana value is the front face's, so its cost is the requirement.
    const cost = spell.manaCost.split(' // ')[0] ?? '';
    const solid = colors.filter(c => solidPips(cost, c) > 0);
    const hybrid = [...cost.matchAll(/\{([WUBRG])\/([WUBRG])\}/g)]
      .map(m => [m[1], m[2]].filter((c): c is MtgColor => colors.includes(c as MtgColor)));
    const gold = solid.length >= 2;
    for (const color of solid) {
      result.push({
        colors: [color],
        title: spell.title,
        pips: solidPips(cost, color),
        turn: spell.turn,
        extra: gold ? 1 : 0,
        drivesTarget: !spell.canWait,
        weight: spell.quantity,
      });
    }
    const involved = colors.filter(c => solid.includes(c) || hybrid.some(h => h.includes(c)));
    const hybridPips = hybrid.filter(h => h.length > 0).length;
    if (involved.length >= 2 && (gold || hybridPips > 0)) {
      result.push({
        colors: involved,
        title: spell.title,
        pips: solid.reduce((s, c) => s + solidPips(cost, c), 0) + hybridPips,
        turn: spell.turn,
        extra: 0,
        drivesTarget: !spell.canWait,
        weight: spell.quantity,
      });
    }
    else if (involved.length === 1 && hybridPips > 0) {
      // Hybrid in a deck playing only one of its colours.
      const color = involved[0]!;
      const existing = result.find(r => r.title === spell.title && r.colors.length === 1 && r.colors[0] === color);
      if (existing != null) {
        existing.pips += hybridPips;
      }
      else {
        result.push({
          colors: [color],
          title: spell.title,
          pips: hybridPips,
          turn: spell.turn,
          extra: 0,
          drivesTarget: !spell.canWait,
          weight: spell.quantity,
        });
      }
    }
  }
  return result;
}

function emptyColorRecord(): Record<MtgColor, number> {
  return { W: 0, U: 0, B: 0, R: 0, G: 0 };
}

// ---------------------------------------------------------------------------
// Non-land sources
// ---------------------------------------------------------------------------

/** A non-land card that counts as part of a source. */
interface Producer {
  colors: MtgColor[];
  source: number;
  /** Counts only for spells of this mana value or more. */
  minMv: number;
  quantity: number;
}

/** Rampant Growth, Cultivate, Three Visits: a land onto the battlefield. */
const LAND_SEARCH = /search your library for [^.]*\b(?:land|plains|island|swamp|mountain|forest) cards?\b[^.]*onto the battlefield/;

const MAKES_TREASURE = /\bcreate (?:a|an|one|two|three|x|\d+) (?:tapped )?treasure/;

/** Spell // land cards (MDFCs): the front is not a land, a later face is. */
export function isMdfcLand(card: { typeLine: string }): boolean {
  const faces = card.typeLine.split(' // ');
  return faces.length > 1
    && !/\bland\b/i.test(faces[0] ?? '')
    && faces.slice(1).some(face => /\bland\b/i.test(face));
}

function producerKind(spell: SpellInfo): ProducerKind | null {
  if (isMdfcLand(spell)) {
    return spell.rarity === 'mythic' ? 'mdfcMythic' : 'mdfc';
  }
  const type = (spell.typeLine.split(' // ')[0] ?? '').toLowerCase();
  const text = spell.oracleText.toLowerCase();
  // Rituals are one-shot mana, not a source.
  const permanent = !/\b(?:instant|sorcery)\b/.test(type);
  if (spell.isManaProducer && permanent && (spell.producedMana ?? []).some(isColor)) {
    return /\bcreature\b/.test(type) ? 'dork' : 'rock';
  }
  if (LAND_SEARCH.test(text)) {
    if (spell.cmc <= 2) {
      return 'ramp2';
    }
    return spell.cmc <= 3 ? 'ramp3' : null;
  }
  if (MAKES_TREASURE.test(text) && spell.cmc <= 3) {
    return 'treasure';
  }
  return null;
}

function nonLandProducers(spells: CastSpell[], colors: MtgColor[], settings: ManaSettings): Producer[] {
  const result: Producer[] = [];
  for (const spell of spells) {
    const kind = producerKind(spell);
    if (kind == null) {
      continue;
    }
    const ratio = settings[kind];
    const text = spell.oracleText.toLowerCase();
    let produced: MtgColor[];
    if (kind === 'ramp2' || kind === 'ramp3') {
      produced = /basic land card|\bland card/.test(text)
        ? colors
        : colors.filter(c => text.includes(BASIC_FOR_COLOR[c].toLowerCase()));
    }
    else if (kind === 'treasure') {
      produced = colors;
    }
    else {
      produced = colors.filter(c => (spell.producedMana ?? []).includes(c));
    }
    if (produced.length === 0 || ratio.source <= 0) {
      continue;
    }
    // A card speeds up only spells cast after it.
    const isMdfc = kind === 'mdfc' || kind === 'mdfcMythic';
    const minMv = isMdfc ? ratio.minMv : Math.max(ratio.minMv, spell.turn + 1);
    result.push({ colors: produced, source: ratio.source, minMv, quantity: spell.quantity });
  }
  return result;
}

/** Land equivalents of cheap ramp and draw, for the land count formula. */
function cheapLandEquivalents(spells: CastSpell[], settings: ManaSettings): number {
  let total = 0;
  for (const spell of spells) {
    if (isMdfcLand(spell) || !isCheapRampOrDraw(spell)) {
      continue;
    }
    const kind = producerKind(spell);
    total += (kind != null ? settings[kind].land : CHEAP_LAND_EQUIVALENT) * spell.quantity;
  }
  return total;
}

// ---------------------------------------------------------------------------
// Land sources
// ---------------------------------------------------------------------------

interface Placed {
  profile: LandProfile;
  quantity: number;
}

interface SourceCount {
  /** Lands making any colour of the set. */
  all: number;
  /** Of those, lands making it untapped on turn one. */
  turnOne: number;
}

/** Source counts per colour set (setKey: 'B', 'BR', ...). */
type Sources = Map<string, SourceCount>;

const sourceOf = (sources: Sources, key: string, turnOne: boolean): number => {
  const s = sources.get(key);
  return s == null ? 0 : turnOne ? s.turnOne : s.all;
};

/**
 * Counts land sources for each colour set.
 *
 * A fetch counts for every colour among the lands it can find in this land
 * base (Bloodstained Mire with a Stomping Ground counts as green): fully when
 * there are at least as many targets of that colour as the colour's most
 * demanding spell has pips, settings.fetchPartial when fewer, not at all
 * without targets. Fetches for a basic land count 2/3 when they reach three
 * or more colours (Karsten). On turn one a fetch needs an untapped target.
 * For a set of colours a fetch counts its best colour.
 */
function countSources(
  lands: Placed[],
  colors: MtgColor[],
  sets: MtgColor[][],
  maxPips: Record<MtgColor, number>,
  settings: ManaSettings,
): Sources {
  const result: Sources = new Map(sets.map(set => [setKey(set), { all: 0, turnOne: 0 }]));
  for (const { profile, quantity } of lands) {
    if (profile.fetch != null) {
      continue;
    }
    for (const set of sets) {
      const inSet = profile.colors.filter(c => set.includes(c));
      if (inSet.length > 0) {
        // A Pathway is one colour or the other: Karsten counts it in full in
        // a two-colour deck and as 2/3 of each colour with three or more.
        // Filter lands ({1}, {T}: Add any colour) cost a mana for each
        // coloured mana: half a source.
        const share = (profile.modal && colors.length >= 3 && inSet.length < profile.colors.length ? 2 / 3 : 1)
          * (profile.costed ? COSTED_SOURCE : 1);
        const entry = result.get(setKey(set))!;
        entry.all += quantity * share;
        if (profile.turnOne) {
          entry.turnOne += quantity * share;
        }
      }
    }
  }
  // Diminishing returns, per colour: every fetch uses up one of the lands it
  // finds, so fetches give at most fetchesPerTarget sources of a colour per
  // fetchable land of that colour. Within that they count in full (in the
  // simulated Gruul land base 8 fetches shared 4 green targets and lost
  // nothing); beyond it each fetch is worth proportionally less, and a new
  // target of the colour lifts the ceiling again.
  const fetchLands = lands.filter(l => l.profile.fetch != null);
  const findable = (l: Placed): boolean => l.profile.fetch == null && fetchLands.some(f =>
    (!f.profile.fetch!.basicOnly || l.profile.kind === 'basic')
    && l.profile.basicTypes.some(t => f.profile.fetch!.types.includes(t)));
  const saturation = emptyColorRecord();
  for (const color of colors) {
    const targetsOfColor = lands.filter(l => findable(l) && l.profile.colors.includes(color))
      .reduce((s, l) => s + l.quantity, 0);
    const fetchesForColor = fetchLands.filter(f => lands.some(l => l.profile.fetch == null
      && l.profile.colors.includes(color)
      && (!f.profile.fetch!.basicOnly || l.profile.kind === 'basic')
      && l.profile.basicTypes.some(t => f.profile.fetch!.types.includes(t))))
      .reduce((s, f) => s + f.quantity, 0);
    saturation[color] = fetchesForColor > 0
      ? Math.min(1, settings.fetchesPerTarget * targetsOfColor / fetchesForColor)
      : 1;
  }
  for (const { profile, quantity } of lands) {
    const fetch = profile.fetch;
    if (fetch == null) {
      continue;
    }
    const targets = lands.filter(l => l.profile.fetch == null
      && (!fetch.basicOnly || l.profile.kind === 'basic')
      && l.profile.basicTypes.some(t => fetch.types.includes(t)));
    const reach = colors.filter(c => targets.some(t => t.profile.colors.includes(c)));
    const spread = fetch.basicOnly && reach.length >= 3 ? 2 / 3 : 1;
    const value = emptyColorRecord();
    const valueTurnOne = emptyColorRecord();
    for (const color of reach) {
      const withColor = targets.filter(t => t.profile.colors.includes(color));
      const count = withColor.reduce((s, t) => s + t.quantity, 0);
      value[color] = (count >= Math.max(1, maxPips[color]) ? 1 : settings.fetchPartial) * spread * saturation[color];
      if (profile.turnOne && withColor.some(t => t.profile.turnOne)) {
        valueTurnOne[color] = value[color];
      }
    }
    for (const set of sets) {
      const entry = result.get(setKey(set))!;
      entry.all += quantity * Math.max(0, ...set.map(c => value[c]));
      entry.turnOne += quantity * Math.max(0, ...set.map(c => valueTurnOne[c]));
    }
  }
  return result;
}

/** Lands any fetch in the land base can find, and the fetches themselves. */
function fetchCounts(lands: Placed[]): { fetches: number; targets: number } {
  const fetches = lands.filter(l => l.profile.fetch != null);
  const targets = lands.filter(l => l.profile.fetch == null && fetches.some(f =>
    (!f.profile.fetch!.basicOnly || l.profile.kind === 'basic')
    && l.profile.basicTypes.some(t => f.profile.fetch!.types.includes(t))));
  return {
    fetches: fetches.reduce((s, l) => s + l.quantity, 0),
    targets: targets.reduce((s, l) => s + l.quantity, 0),
  };
}

/**
 * P(at least one fetch among the first `seen` cards, and more fetches plus
 * targets seen than there are targets): a fetch then has nothing left to
 * find. Treats all fetches as sharing all targets, so it slightly
 * overstates the risk when fetches find different lands.
 */
export function deadFetchChance(deckSize: number, fetches: number, targets: number, seen: number): number {
  if (fetches <= 0) {
    return 0;
  }
  const rest = deckSize - fetches - targets;
  const total = logBinomial(deckSize, seen);
  let chance = 0;
  for (let f = 1; f <= Math.min(fetches, seen); f++) {
    for (let t = Math.max(0, targets + 1 - f); t <= Math.min(targets, seen - f); t++) {
      chance += Math.exp(logBinomial(fetches, f) + logBinomial(targets, t) + logBinomial(rest, seen - f - t) - total);
    }
  }
  return chance;
}

/**
 * Expected share of the deck's colour needs castable on curve, given the
 * land sources. One-drops count only turn-one sources; producers count for
 * the spells they can speed up; gold spells need their extra source.
 */
function castableValue(
  deckSize: number,
  lands: number,
  reqs: Requirement[],
  commanderFormat: boolean,
  producerSources: (set: MtgColor[], turn: number) => number,
): (sources: Sources) => number {
  const totalWeight = reqs.reduce((s, r) => s + r.weight, 0) || 1;
  const grouped = new Map<string, { key: string; set: MtgColor[]; pips: number; turn: number; extra: number; weight: number }>();
  for (const r of reqs) {
    const key = `${setKey(r.colors)}:${r.pips}:${r.turn}:${r.extra}`;
    const entry = grouped.get(key) ?? { key: setKey(r.colors), set: r.colors, pips: r.pips, turn: r.turn, extra: r.extra, weight: 0 };
    entry.weight += r.weight;
    grouped.set(key, entry);
  }
  const prob = (pips: number, turn: number, k: number): number =>
    castOnCurveProbability(deckSize, lands, k, pips, turn, commanderFormat);

  return sources => {
    let value = 0;
    for (const { key, set, pips, turn, extra, weight } of grouped.values()) {
      const s = Math.max(0, Math.min(lands, sourceOf(sources, key, turn === 1) + producerSources(set, turn) - extra));
      const lo = Math.floor(s);
      const frac = s - lo;
      const p = frac > 0
        ? prob(pips, turn, lo) * (1 - frac) + prob(pips, turn, Math.min(lands, lo + 1)) * frac
        : prob(pips, turn, lo);
      value += weight * p;
    }
    return value / totalWeight;
  };
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

/** A land target: one colour or a set, all sources or untapped turn-one ones. */
interface Group {
  colors: MtgColor[];
  key: string;
  turnOne: boolean;
  /** Land sources wanted (the driver's sources minus producers). */
  target: number;
  driver: Requirement;
  /** The driver's sources wanted, producers included. */
  sources: number;
  unreachable: boolean;
}

/** Builds a land base proposal. */
export function planLandBase(input: LandBaseInput): LandBasePlan {
  const colors = ALL_COLORS.filter(c => input.deckColors.includes(c));
  const settings = resolveManaSettings(input.settings);
  const spells = castSpells(input.spells, settings);
  const commander = input.commander != null ? castSpells([input.commander], settings) : [];
  const sideboard = settings.includeSideboard ? castSpells(input.sideboard ?? [], settings) : [];

  // Non-land sources.
  const producers = nonLandProducers(spells, colors, settings);
  const producerSources = (set: MtgColor[], turn: number): number => producers
    .filter(p => p.minMv <= turn && p.colors.some(c => set.includes(c)))
    .reduce((s, p) => s + p.source * p.quantity, 0);
  const mdfcLands = spells
    .filter(isMdfcLand)
    .reduce((s, c) => s + settings[c.rarity === 'mythic' ? 'mdfcMythic' : 'mdfc'].land * c.quantity, 0);

  // Land count: the formula less the land share of MDFCs.
  const spellCount = spells.reduce((s, c) => s + c.quantity, 0);
  const avgCmc = spellCount > 0 ? spells.reduce((s, c) => s + c.cmc * c.quantity, 0) / spellCount : 0;
  const cheapRampDraw = spells.reduce((s, c) => s + (isCheapRampOrDraw(c) ? c.quantity : 0), 0);
  const formula = recommendedLandCount(
    avgCmc,
    cheapLandEquivalents(spells, settings) / CHEAP_LAND_EQUIVALENT,
    input.deckSize,
  );
  const chosen = input.landCountOverride != null && input.landCountOverride > 0
    ? input.landCountOverride
    : settings.landCount;
  const formulaLandCount = Math.max(1, formula.count - Math.round(mdfcLands));
  const landCount = chosen != null && chosen > 0 ? Math.round(chosen) : formulaLandCount;

  // Targets: per colour set, all sources (two-drops and up) and untapped
  // turn-one sources (one-drops), in lands.
  const reqs = requirements([...spells, ...commander, ...sideboard], colors);
  const maxPips = emptyColorRecord();
  for (const req of reqs) {
    for (const color of req.colors) {
      maxPips[color] = Math.max(maxPips[color], req.pips);
    }
  }
  // Most pips of one colour on a single spell: the basics it needs under
  // Blood Moon. Gold and hybrid unions are left out.
  const solidMaxPips = emptyColorRecord();
  for (const req of reqs) {
    if (req.colors.length === 1) {
      solidMaxPips[req.colors[0]!] = Math.max(solidMaxPips[req.colors[0]!], req.pips);
    }
  }
  const groups = new Map<string, Group>();
  for (const req of reqs.filter(r => r.drivesTarget)) {
    const needed = sourcesNeeded(input.deckSize, landCount, req.pips, req.turn, input.commanderFormat);
    const sources = Math.min(landCount, needed.sources + req.extra);
    const unreachable = needed.unreachable || needed.sources + req.extra > landCount;
    const target = Math.max(0, sources - producerSources(req.colors, req.turn));
    const turnOne = req.turn === 1;
    const key = `${setKey(req.colors)}:${turnOne ? 1 : 0}`;
    const current = groups.get(key);
    const better = current == null
      || target > current.target
      || (target === current.target && req.turn < current.driver.turn);
    if (better) {
      groups.set(key, { colors: req.colors, key: setKey(req.colors), turnOne, target, driver: req, sources, unreachable });
    }
  }
  const groupList = [...groups.values()];
  const sets = [
    ...colors.map(c => [c]),
    ...[...new Map(groupList.filter(g => g.colors.length > 1).map(g => [g.key, g.colors])).values()],
  ];

  // Pip share, for spending surplus slots.
  const pipTotals = emptyColorRecord();
  for (const req of reqs) {
    if (req.colors.length === 1) {
      pipTotals[req.colors[0]!] += req.pips;
    }
  }
  const pipSum = colors.reduce((s, c) => s + pipTotals[c], 0);
  const share = (c: MtgColor): number => (pipSum > 0 ? pipTotals[c] / pipSum : 1 / Math.max(1, colors.length));

  // Lands already in the deck can always stay, even when the collection
  // counts the copy as used by another deck or does not list it at all.
  const currentQty = new Map<string, number>();
  for (const cl of input.currentLands) {
    currentQty.set(cl.land.title, (currentQty.get(cl.land.title) ?? 0) + cl.quantity);
  }
  const options: LandOption[] = input.options.map(o => {
    const inDeck = currentQty.get(o.land.title) ?? 0;
    return inDeck > 0 ? { ...o, available: Math.max(o.available, inDeck), free: Math.max(o.free, inDeck) } : o;
  });
  for (const cl of input.currentLands) {
    if (/\bbasic\b/i.test(cl.land.typeLine) || options.some(o => o.land.title === cl.land.title)) {
      continue;
    }
    const inDeck = currentQty.get(cl.land.title) ?? 0;
    options.push({ land: cl.land, cardId: null, available: inDeck, free: inDeck, owned: inDeck, usedIn: [], price: null });
  }

  // Utility lands already in the deck stay.
  const currentProfiled = input.currentLands.map(cl => ({
    ...cl,
    profile: landProfile(cl.land, colors, input.commanderFormat),
  }));
  const picks = new Map<string, LandPick>();
  let slots = landCount;
  for (const cl of currentProfiled) {
    // Utility lands, and lands the deck asks to keep, stay as they are.
    if ((cl.profile.kind !== 'utility' && !settings.keepLands.includes(cl.land.title)) || slots <= 0) {
      continue;
    }
    const quantity = Math.min(cl.quantity, slots);
    const option = options.find(o => o.land.title === cl.land.title);
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

  // Improving, not rebuilding: a deck with lands keeps them all, and lands
  // are only swapped later when that clearly closes a colour shortfall.
  // Tested decks that meet their targets get no changes. With a lower land
  // count, basics go first.
  const improving = input.rebuild !== true && input.currentLands.some(cl => cl.quantity > 0);
  if (improving) {
    const rest = currentProfiled
      .filter(cl => !picks.has(cl.land.title))
      .sort((a, b) => (a.profile.kind === 'basic' ? 1 : 0) - (b.profile.kind === 'basic' ? 1 : 0));
    for (const cl of rest) {
      const quantity = Math.min(cl.quantity, slots);
      if (quantity <= 0) {
        continue;
      }
      const option = options.find(o => o.land.title === cl.land.title);
      picks.set(cl.land.title, {
        option: option ?? { land: cl.land, cardId: null, available: quantity, free: quantity, owned: quantity, usedIn: [], price: null },
        profile: cl.profile,
        quantity: (picks.get(cl.land.title)?.quantity ?? 0) + quantity,
        missing: 0,
        kept: false,
      });
      slots -= quantity;
    }
  }

  // Spell // land cards are spells first: never suggested as a land.
  const candidates = [
    ...colors.map(basicOption),
    ...options.filter(o => !/\bbasic\b/i.test(o.land.typeLine) && !isMdfcLand(o.land)),
  ].map(option => ({ option, profile: landProfile(option.land, colors, input.commanderFormat) }))
    .filter(c => c.profile.colors.length > 0 || c.profile.fetch != null);

  const count = (lands: Placed[]): Sources => countSources(lands, colors, sets, maxPips, settings);
  // Fetches the plan has or may still pick.
  const fetchProfiles = [
    ...candidates.filter(c => c.profile.fetch != null && c.option.available > 0).map(c => c.profile),
    ...[...picks.values()].filter(p => p.profile.fetch != null).map(p => p.profile),
  ];
  // Domain cards (Leyline Binding) get cheaper with each basic land type.
  const hasDomain = [...spells, ...commander].some(s => /domain/i.test(s.oracleText));
  const fetchable = (profile: LandProfile): boolean => profile.fetch == null && fetchProfiles.some(f =>
    (!f.fetch!.basicOnly || profile.kind === 'basic') && profile.basicTypes.some(t => f.fetch!.types.includes(t)));
  const placedOf = (): Placed[] => [...picks.values()].map(p => ({ profile: p.profile, quantity: p.quantity }));
  const tappedLimit = Math.round(TAPPED_LIMIT_60 * input.deckSize / 60);
  let tappedUsed = [...picks.values()].reduce((s, p) => s + p.profile.tappedWeight * p.quantity, 0);

  // While a target is short, a land is worth the share of each target it
  // still has to close (shortfall / target), so the largest relative
  // shortfall goes first and a shortfall that cannot be closed ends up
  // shared in proportion to the targets. Once every target is met, a land is
  // worth how many more coloured spells it makes castable on curve. Sources
  // are recounted with each candidate, so a typed dual also gains the value
  // it adds to fetches already picked.
  const castValue = castableValue(input.deckSize, landCount, reqs, input.commanderFormat, producerSources);
  let tappedPicked = 0;
  let drawbackPicked = [...picks.values()].reduce((s, p) => s + (p.profile.drawback ? p.quantity : 0), 0);
  for (let i = 0; i < slots; i++) {
    const placed = placedOf();
    const before = count(placed);
    const typesPresent = new Set(placed.filter(p => p.profile.fetch == null).flatMap(p => p.profile.basicTypes));
    // Once the slots left are only enough for the basics each colour still
    // needs, only those basics can be picked.
    const basicsOf = (color: MtgColor): number => [...picks.values()]
      .filter(p => p.profile.kind === 'basic' && p.profile.colors.includes(color))
      .reduce((s, p) => s + p.quantity, 0);
    const basicsShort = colors.filter(c => settings.minBasics[c] > basicsOf(c));
    const basicsNeeded = basicsShort.reduce((s, c) => s + settings.minBasics[c] - basicsOf(c), 0);
    const basicsOnly = basicsNeeded > 0 && basicsNeeded >= slots - i;
    const shortfall = (g: Group, s: Sources): number => g.target - sourceOf(s, g.key, g.turnOne);
    const short = groupList.some(g => shortfall(g, before) > 1e-9);
    // When the remaining slots can close every shortfall one colour at a
    // time, a land's second colour is only a bonus, so tapped duals are not
    // needed. Otherwise lands that close two shortfalls at once are.
    const shortfallTotal = colors.reduce((s, c) => s + Math.ceil(Math.max(
      0,
      ...groupList.filter(g => g.key === c).map(g => shortfall(g, before)),
    ) - 1e-9), 0);
    const doubleCounts = shortfallTotal > slots - i;
    const closes = (g: Group, after: Sources): number => {
      const open = Math.max(0, shortfall(g, before));
      const closed = Math.min(open, Math.max(0, shortfall(g, before) - shortfall(g, after)));
      return g.target > 0 ? closed * open / g.target : 0;
    };
    const beforeValue = short ? 0 : castValue(before);

    let best: { option: LandOption; profile: LandProfile; score: number } | null = null;
    for (const cand of candidates) {
      const used = picks.get(cand.option.land.title)?.quantity ?? 0;
      const isBasic = cand.profile.kind === 'basic';
      const limit = isBasic ? cand.option.available : Math.min(cand.option.available, input.maxCopies);
      const neededBasic = isBasic && cand.profile.colors.some(c => basicsShort.includes(c));
      if (used >= limit || tappedUsed + cand.profile.tappedWeight > tappedLimit + 1e-9 || (basicsOnly && !neededBasic)) {
        continue;
      }
      const after = count([...placed, { profile: cand.profile, quantity: 1 }]);
      let gain: number;
      if (short) {
        const values = colors.map(color => groupList
          .filter(g => g.key === color)
          .reduce((s, g) => s + closes(g, after), 0));
        const sum = values.reduce((s, v) => s + v, 0);
        const top = Math.max(0, ...values);
        const union = groupList.filter(g => g.colors.length > 1).reduce((s, g) => s + closes(g, after), 0);
        gain = (doubleCounts ? sum : top + EXTRA_COLOUR_WEIGHT * (sum - top)) + union;
      }
      else {
        // A second source of a colour can be worth far more than the first
        // (a GG spell needs both), so a land is worth the best average gain
        // of adding 1, 2 or 3 copies of it.
        gain = -Infinity;
        for (let copies = 1; copies <= LOOKAHEAD_COPIES && copies <= Math.min(limit - used, slots - i); copies++) {
          const more = copies === 1 ? after : count([...placed, { profile: cand.profile, quantity: copies }]);
          const value = castValue(more) - beforeValue + colors.reduce((s, color) =>
            s + SURPLUS_WEIGHT * share(color) * (sourceOf(more, color, false) - sourceOf(before, color, false)), 0);
          gain = Math.max(gain, value / copies);
        }
      }
      let score = gain * (short ? SHORTFALL_SPEED_FACTOR : SPEED_FACTOR)[cand.profile.speed];
      if (!short && cand.profile.speed === 'tapped') {
        score *= TAPPED_DECAY ** tappedPicked;
      }
      if (cand.profile.heavyDrawback) {
        score *= HEAVY_PAIN_FACTOR;
      }
      else if (cand.profile.painful) {
        score *= cand.profile.painEveryTap ? PAIN_EVERY_TAP_FACTOR : PAIN_FACTOR;
      }
      // Fetches already work as painless rainbow lands through the lands
      // they find: a Tundra or Island strengthens every Flooded Strand, a
      // City of Brass none of them.
      // Basics beyond what each colour needs under Blood Moon (as many as
      // its most demanding spell has pips, or the deck's minimum) bring only
      // colour, so a land of that colour with an ability, such as Karakas,
      // wins over them: after the first Plains for {W}, the second for
      // {W}{W}.
      const excessBasic = isBasic && cand.profile.colors.every(c =>
        basicsOf(c) >= Math.max(1, settings.minBasics[c], solidMaxPips[c]));
      if (fetchable(cand.profile) && !excessBasic) {
        score *= FETCHABLE_BONUS;
      }
      if (cand.profile.upside) {
        score *= UPSIDE_BONUS;
      }
      if (hasDomain) {
        score *= 1 + DOMAIN_TYPE_BONUS * cand.profile.basicTypes.filter(t => !typesPresent.has(t)).length;
      }
      // One City of Brass is fine; eight lands that hurt or feed the
      // opponent on every tap add up.
      if (cand.profile.drawback) {
        score *= DRAWBACK_DECAY ** drawbackPicked;
      }
      if (cand.profile.costed) {
        score *= COSTED_FACTOR;
      }
      // A shockland costs 2 life to enter untapped: a real dual does not.
      if (cand.profile.shock) {
        score *= SHOCK_FACTOR;
      }
      // The deck owner's own non-basic choices (Karakas, a Savannah) win
      // near ties over basics and other lands.
      if (!isBasic && (currentQty.get(cand.option.land.title) ?? 0) > used) {
        score *= CURRENT_BONUS;
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
    tappedUsed += best.profile.tappedWeight;
    if (best.profile.speed === 'tapped') {
      tappedPicked += 1;
    }
    if (best.profile.drawback) {
      drawbackPicked += 1;
    }
  }

  if (improving) {
    swapToCloseShortfalls();
  }

  /**
   * Swaps one land for another while that clearly closes a colour shortfall:
   * the swap must close at least MIN_SWAP_GAIN of a target, weighed by the
   * same land qualities as the fill. Never polishes a land base whose
   * targets are met.
   */
  function swapToCloseShortfalls(): void {
    // Tested decks often sit a source or two under Karsten's numbers on
    // purpose, so a target within tolerance counts as met here.
    const tolerated = (g: Group): number => g.target - Math.max(1, SWAP_TOLERANCE * g.target);
    const relativeShortfall = (s: Sources): number => groupList.reduce((t, g) =>
      t + (g.target > 0 ? Math.max(0, tolerated(g) - sourceOf(s, g.key, g.turnOne)) / g.target : 0), 0);
    const quality = (profile: LandProfile): number => {
      let q = SHORTFALL_SPEED_FACTOR[profile.speed];
      if (profile.heavyDrawback) {
        q *= HEAVY_PAIN_FACTOR;
      }
      else if (profile.painful) {
        q *= profile.painEveryTap ? PAIN_EVERY_TAP_FACTOR : PAIN_FACTOR;
      }
      else if (profile.drawback) {
        // Forbidden Orchard: every tap gives the opponent a creature.
        q *= PAIN_EVERY_TAP_FACTOR;
      }
      if (profile.costed) {
        q *= COSTED_FACTOR;
      }
      if (profile.shock) {
        q *= SHOCK_FACTOR;
      }
      if (fetchable(profile)) {
        q *= FETCHABLE_BONUS;
      }
      // A fetch in the deck also shuffles (Brainstorm), thins the deck and
      // triggers landfall, so swapping it out needs more.
      if (profile.upside || profile.fetch != null) {
        q *= UPSIDE_BONUS;
      }
      return q;
    };
    const basicsOf = (color: MtgColor): number => [...picks.values()]
      .filter(p => p.profile.kind === 'basic' && p.profile.colors.includes(color))
      .reduce((s, p) => s + p.quantity, 0);

    for (let iteration = 0; iteration < landCount; iteration++) {
      const placed = placedOf();
      const shortBefore = relativeShortfall(count(placed));
      const castBefore = castValue(count(placed));
      if (shortBefore < 1e-9) {
        return;
      }
      const shortColors = new Set(groupList
        .filter(g => tolerated(g) - sourceOf(count(placed), g.key, g.turnOne) > 1e-9)
        .flatMap(g => g.colors));
      const helpful = candidates.filter(c => c.profile.fetch != null || c.profile.colors.some(col => shortColors.has(col)));
      let best: { remove: LandPick; add: { option: LandOption; profile: LandProfile }; score: number } | null = null;
      for (const remove of picks.values()) {
        // Utility lands and lands the deck asks to keep stay; so do basics
        // the deck's minimum needs.
        if (remove.kept || remove.quantity <= 0
          || (remove.profile.kind === 'basic' && remove.profile.colors.some(c => basicsOf(c) <= settings.minBasics[c]))) {
          continue;
        }
        const without = placed.map(p => (p.profile === remove.profile ? { ...p, quantity: p.quantity - 1 } : p));
        for (const add of helpful) {
          if (add.option.land.title === remove.option.land.title) {
            continue;
          }
          const used = picks.get(add.option.land.title)?.quantity ?? 0;
          const limit = add.profile.kind === 'basic' ? add.option.available : Math.min(add.option.available, input.maxCopies);
          if (used >= limit
            || tappedUsed - remove.profile.tappedWeight + add.profile.tappedWeight > tappedLimit + 1e-9) {
            continue;
          }
          const after = count([...without, { profile: add.profile, quantity: 1 }]);
          const gain = shortBefore - relativeShortfall(after);
          // A non-basic the deck chose (a manland, Bojuka Bog, a Bridge in
          // Affinity) may be there for reasons the suggester cannot see, so
          // removing one needs twice the evidence.
          const evidence = remove.profile.kind === 'basic' ? 1 : NONBASIC_REMOVAL_EVIDENCE;
          const score = gain * quality(add.profile) / quality(remove.profile);
          if (score < MIN_SWAP_GAIN * evidence || castValue(after) - castBefore < MIN_CASTABLE_GAIN * evidence) {
            continue;
          }
          if (best == null || score > best.score + 1e-9) {
            best = { remove, add, score };
          }
        }
      }
      if (best == null) {
        return;
      }
      best.remove.quantity -= 1;
      if (best.remove.quantity <= 0) {
        picks.delete(best.remove.option.land.title);
      }
      const existing = picks.get(best.add.option.land.title);
      picks.set(best.add.option.land.title, {
        option: best.add.option,
        profile: best.add.profile,
        quantity: (existing?.quantity ?? 0) + 1,
        missing: 0,
        kept: false,
      });
      tappedUsed += best.add.profile.tappedWeight - best.remove.profile.tappedWeight;
    }
  }

  for (const pick of picks.values()) {
    pick.missing = pick.profile.kind === 'basic' || pick.kept
      ? 0
      : Math.max(0, pick.quantity - pick.option.free);
  }

  // Before and after.
  const proposedPlaced = placedOf();
  const currentLandCount = input.currentLands.reduce((s, l) => s + l.quantity, 0);
  const currentSources = count(currentProfiled);
  const proposedSources = count(proposedPlaced);
  const proposedLandCount = proposedPlaced.reduce((s, p) => s + p.quantity, 0);
  const currentValue = castableValue(input.deckSize, currentLandCount, reqs, input.commanderFormat, producerSources);
  const prob = (g: Group, lands: number, src: number): number =>
    castOnCurveProbability(input.deckSize, lands, src - g.driver.extra, g.driver.pips, g.driver.turn, input.commanderFormat);
  const colorTargets: ColorTarget[] = colors.map(color => {
    const anyGroup = groups.get(`${color}:0`);
    const oneGroup = groups.get(`${color}:1`);
    const main = anyGroup ?? oneGroup ?? null;
    const fromProducers = main != null ? producerSources([color], main.driver.turn) : 0;
    const current = sourceOf(currentSources, color, main?.turnOne ?? false) + fromProducers;
    const proposed = sourceOf(proposedSources, color, main?.turnOne ?? false) + fromProducers;
    return {
      color,
      target: main?.sources ?? 0,
      driver: main != null ? { title: main.driver.title, pips: main.driver.pips, turn: main.driver.turn } : null,
      goal: castGoal(main?.driver.turn ?? 1),
      unreachable: main?.unreachable ?? false,
      fromProducers,
      current,
      proposed,
      probCurrent: main != null ? prob(main, currentLandCount, current) : 1,
      probProposed: main != null ? prob(main, proposedLandCount, proposed) : 1,
      turnOne: oneGroup != null
        ? {
          target: oneGroup.sources,
          unreachable: oneGroup.unreachable,
          current: sourceOf(currentSources, color, true) + producerSources([color], 1),
          proposed: sourceOf(proposedSources, color, true) + producerSources([color], 1),
        }
        : null,
    };
  });
  const unionTargets: UnionTarget[] = groupList
    .filter(g => g.colors.length > 1)
    .map(g => {
      const fromProducers = producerSources(g.colors, g.driver.turn);
      return {
        colors: g.colors,
        driver: { title: g.driver.title, pips: g.driver.pips, turn: g.driver.turn },
        target: g.sources,
        unreachable: g.unreachable,
        current: sourceOf(currentSources, g.key, g.turnOne) + fromProducers,
        proposed: sourceOf(proposedSources, g.key, g.turnOne) + fromProducers,
      };
    })
    .sort((a, b) => setKey(a.colors).localeCompare(setKey(b.colors)));

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

  const tappedOf = (lands: Placed[]): number => lands.reduce((s, l) => s + l.profile.tappedWeight * l.quantity, 0);
  const fetchInfo = fetchCounts(proposedPlaced);
  const extraDraw = input.commanderFormat ? 1 : 0;

  return {
    landCount,
    landCountFormula: formula.formula,
    formulaLandCount,
    avgCmc,
    cheapRampDraw,
    currentLandCount,
    mdfcLands,
    tappedLimit,
    tappedCurrent: tappedOf(currentProfiled),
    tappedProposed: tappedOf(proposedPlaced),
    deadFetch: fetchInfo.fetches > 0
      ? DEAD_FETCH_TURNS.map(turn => ({
        turn,
        chance: deadFetchChance(input.deckSize, fetchInfo.fetches, fetchInfo.targets, 7 + turn - 1 + extraDraw),
      }))
      : [],
    unionTargets,
    alternateCosts: alternateCostCards(
      [...input.spells, ...(input.commander != null ? [input.commander] : [])],
      settings,
    ),
    castableCurrent: reqs.length > 0 ? currentValue(currentSources) : 1,
    castableProposed: reqs.length > 0 ? castValue(proposedSources) : 1,
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
  // In cardbase mode a land you own wins a true tie, so less has to be
  // bought; it never beats a better land or a basic.
  const candOwned = cand.option.free > 0 ? 0 : 1;
  const bestOwned = best.option.free > 0 ? 0 : 1;
  if (candOwned !== bestOwned) {
    return candOwned - bestOwned;
  }
  const candPrice = cand.option.price ?? Infinity;
  const bestPrice = best.option.price ?? Infinity;
  if (candPrice !== bestPrice) {
    return candPrice - bestPrice;
  }
  return cand.option.land.title.localeCompare(best.option.land.title);
}
