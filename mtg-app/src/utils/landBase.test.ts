/// <reference types="vite/client" />
import { describe, expect, it } from 'vitest';
import {
  DEFAULT_MANA_SETTINGS,
  alternateCostCards,
  castGoal,
  manaSettingsDiff,
  manaValueOf,
  parseManaSettings,
  castOnCurveProbability,
  deadFetchChance,
  resolveManaSettings,
  landProfile,
  planLandBase,
  recommendedLandCount,
  solidPips,
  sourcesNeeded,
  type LandBaseInput,
  type LandInfo,
  type LandOption,
  type ManaSettings,
  type SpellInfo,
} from './landBase';
import fixtures from './__fixtures__/cards.json';

// The user's decklists are git-ignored personal data: present on their
// machine only. Without the file the test-deck tests are skipped.
const testDeckFiles = import.meta.glob<unknown>('./__fixtures__/testDecks.json', { eager: true, import: 'default' });
const testDecks = Object.values(testDeckFiles)[0] ?? [];

const CARDS = new Map(fixtures.map(c => [c.title, c]));

function land(title: string): LandInfo {
  const c = CARDS.get(title);
  if (c == null) {
    throw new Error(`Fixture missing: ${title}`);
  }
  return { title: c.title, typeLine: c.typeLine, oracleText: c.oracleText, producedMana: c.producedMana };
}

function option(title: string, overrides: Partial<LandOption> = {}): LandOption {
  return {
    land: land(title),
    cardId: title,
    available: Infinity,
    free: 0,
    owned: 0,
    usedIn: [],
    price: 1,
    ...overrides,
  };
}

function spell(title: string, manaCost: string, cmc: number, quantity = 1, extra: Partial<SpellInfo> = {}): SpellInfo {
  return {
    title,
    typeLine: 'Instant',
    oracleText: '',
    cmc,
    isManaProducer: false,
    producedMana: [],
    manaCost,
    quantity,
    ...extra,
  };
}

describe('castOnCurveProbability / sourcesNeeded', () => {
  // Karsten, "How Many Sources Do You Need to Consistently Cast Your Spells?
  // A 2022 Update" (TCGplayer): [cost, mana value, pips, 60, 80, 99, 40].
  // His assumed land counts: 60 -> 25, 80 -> 35, 99 -> 41 (Commander), 40 -> 17.
  const KARSTEN_2022: [string, number, number, number, number, number, number][] = [
    ['5C', 6, 1, 9, 12, 14, 6],
    ['4C', 5, 1, 9, 14, 15, 6],
    ['3C', 4, 1, 10, 15, 16, 7],
    ['2C', 3, 1, 12, 16, 18, 8],
    ['5CC', 7, 2, 12, 17, 20, 8],
    ['1C', 2, 1, 13, 18, 19, 9],
    ['4CC', 6, 2, 13, 19, 22, 9],
    ['C', 1, 1, 14, 19, 19, 9],
    ['3CC', 5, 2, 15, 20, 23, 10],
    ['4CCC', 7, 3, 16, 22, 26, 10],
    ['2CC', 4, 2, 16, 23, 26, 11],
    ['3CCC', 6, 3, 17, 24, 28, 11],
    ['1CC', 3, 2, 18, 25, 28, 12],
    ['2CCC', 5, 3, 19, 26, 30, 13],
    ['CC', 2, 2, 21, 28, 30, 14],
    ['1CCC', 4, 3, 21, 29, 33, 14],
    ['1CCCC', 5, 4, 22, 31, 36, 15],
    ['CCC', 3, 3, 23, 32, 36, 16],
    ['CCCC', 4, 4, 24, 34, 39, 17],
  ];
  const SIZES: { deck: number; lands: number; column: number; commander: boolean }[] = [
    { deck: 60, lands: 25, column: 3, commander: false },
    { deck: 80, lands: 35, column: 4, commander: false },
    { deck: 99, lands: 41, column: 5, commander: true },
    { deck: 40, lands: 17, column: 6, commander: false },
  ];
  const cases = SIZES.flatMap(size => KARSTEN_2022.map(row => [
    `${row[0]} in ${size.deck} cards`, size, row[1], row[2], row[size.column] as number,
  ] as const));

  it('covers all 76 table values', () => {
    expect(cases).toHaveLength(76);
  });

  it.each(cases)('%s matches Karsten within one source', (_name, size, turn, pips, karsten) => {
    const { sources, unreachable } = sourcesNeeded(size.deck, size.lands, pips, turn, size.commander);
    expect(unreachable).toBe(false);
    expect(Math.abs(sources - karsten)).toBeLessThanOrEqual(1);
  });

  it('asks 89% plus mana value, capped at 96%', () => {
    expect(castGoal(1)).toBeCloseTo(0.9, 9);
    expect(castGoal(4)).toBeCloseTo(0.93, 9);
    expect(castGoal(7)).toBeCloseTo(0.96, 9);
    expect(castGoal(9)).toBeCloseTo(0.96, 9);
  });

  it('gives Commander decks a better chance through the free mulligan and draw', () => {
    expect(castOnCurveProbability(99, 41, 19, 1, 2, true)).toBeGreaterThan(castOnCurveProbability(99, 41, 19, 1, 2));
  });

  it('is 1 when every land makes the colour', () => {
    expect(castOnCurveProbability(60, 24, 24, 1, 2)).toBeCloseTo(1, 6);
  });

  it('is 0 without sources', () => {
    expect(castOnCurveProbability(60, 24, 0, 1, 2)).toBe(0);
  });

  it('flags impossible targets', () => {
    expect(sourcesNeeded(60, 10, 3, 1).unreachable).toBe(true);
  });
});

/**
 * The user's own "normal" decks, exported from their database. Hyper Heroic
 * is left out on purpose: it runs 17 lands by long testing and is no
 * benchmark. manaSettings holds the deck's own changes, such as a realistic
 * cost for Walk-In Closet.
 */
interface TestDeck {
  title: string;
  format: string;
  manaSettings: Partial<ManaSettings>;
  commander: (SpellInfo & { rarity: string }) | null;
  cards: (SpellInfo & { rarity: string })[];
}

const TEST_DECKS = testDecks as TestDeck[];

function testDeck(title: string): TestDeck {
  const deck = TEST_DECKS.find(d => d.title === title);
  if (deck == null) {
    throw new Error(`Test deck missing: ${title}`);
  }
  return deck;
}

const isFrontLand = (card: SpellInfo): boolean => /\bland\b/i.test(card.typeLine.split(' // ')[0]!);

/** Plans a test deck from scratch, with only basics, at the formula's count. */
function planTestDeck(deck: TestDeck, landCountOverride: number | null = null) {
  const spells = deck.cards.filter(c => !isFrontLand(c));
  const lands = deck.cards.filter(isFrontLand);
  const costs = [...spells, ...(deck.commander != null ? [deck.commander] : [])].map(c => c.manaCost).join('');
  const deckColors = (['W', 'U', 'B', 'R', 'G'] as const).filter(c => costs.includes(c));
  const commanderFormat = deck.commander != null;
  const plan = planLandBase({
    spells,
    commander: deck.commander,
    currentLands: lands.map(l => ({ land: l, quantity: l.quantity })),
    options: [],
    deckColors: commanderFormat ? ['W', 'U', 'B', 'R', 'G'] : [...deckColors],
    deckSize: deck.cards.reduce((s, c) => s + c.quantity, 0),
    maxCopies: commanderFormat ? 1 : 4,
    commanderFormat,
    landCountOverride,
    settings: deck.manaSettings,
  });
  return { plan, actualLands: lands.reduce((s, c) => s + c.quantity, 0) };
}

describe.skipIf(TEST_DECKS.length === 0)('test decks', () => {
  // Baseline before effective costs, cycling and MDFC handling: [deck, lands
  // the deck runs, formula count]. Later steps should move the formula closer
  // to the deck's own count; update these numbers on purpose when they do.
  // The deck's own count is the user's tested choice, not an error.
  it.each([
    ['Tortured Existence', 23, 23],
    ['UB Exhume', 18, 22],
    // Two MDFCs each: 0.8 land, so one land less than the plain formula.
    ['Bant Miracles', 22, 28],
    ['Bant Control', 22, 27],
    ['Go-Shintai: No Creature Zone', 33, 42],
  ] as const)('%s runs %i lands; the formula says %i', (title, actual, formula) => {
    const { plan, actualLands } = planTestDeck(testDeck(title));
    expect(actualLands).toBe(actual);
    expect(plan.landCount).toBe(formula);
  });

  it('plans Go-Shintai as a five-colour Commander deck', () => {
    const { plan } = planTestDeck(testDeck('Go-Shintai: No Creature Zone'), 33);
    expect(plan.targets.map(t => t.color)).toEqual(['W', 'U', 'B', 'R', 'G']);
    expect(plan.picks.reduce((s, p) => s + p.quantity, 0)).toBe(33);
    for (const t of plan.targets) {
      expect(t.goal).toBeGreaterThanOrEqual(0.9);
      expect(t.goal).toBeLessThanOrEqual(0.96);
    }
  });
});

/** A land not in the card fixture. */
function customLand(title: string, typeLine: string, oracleText: string, producedMana: string[]): LandInfo {
  return { title, typeLine, oracleText, producedMana };
}

const DIMIR_TAPLAND = customLand(
  'Dimir Tapland',
  'Land — Island Swamp',
  'This land enters tapped.\n{T}: Add {U} or {B}.',
  ['U', 'B'],
);

/** Plans a U/B deck that keeps its current lands as they are. */
function dimir(currentLands: { land: LandInfo; quantity: number }[], extra: Partial<LandBaseInput> = {}) {
  const lands = currentLands.reduce((s, l) => s + l.quantity, 0);
  return planLandBase({
    spells: [spell('Counterspell', '{U}{U}', 2, 4), spell('Doom Blade', '{1}{B}', 2, 4), spell('Fatty', '{5}', 5, 28)],
    commander: null,
    currentLands,
    options: [],
    deckColors: ['U', 'B'],
    deckSize: 60,
    maxCopies: 4,
    commanderFormat: false,
    landCountOverride: lands,
    ...extra,
  });
}

const BASIC_SWAMP = customLand('Swamp', 'Basic Land — Swamp', '({T}: Add {B}.)', ['B']);

describe('fetches', () => {
  const current = (plan: ReturnType<typeof dimir>, color: string) => plan.targets.find(t => t.color === color)!.current;

  it('count for every colour among the lands they can find', () => {
    // Marsh Flats names Plains and Swamp; Watery Grave is a Swamp, so the
    // fetch is also a blue source in a deck without Plains.
    const plan = dimir([
      { land: land('Marsh Flats'), quantity: 4 },
      { land: land('Watery Grave'), quantity: 4 },
      { land: land('Island'), quantity: 8 },
      { land: BASIC_SWAMP, quantity: 8 },
    ]);
    expect(current(plan, 'U')).toBe(16);
    expect(current(plan, 'B')).toBe(16);
  });

  it('match the fetch simulation: a Gruul land base has 16 green sources, not 12', () => {
    // Simulated: GG on turn 2 is as castable as with 16 plain green sources.
    const fetchland = (title: string, types: string) => customLand(
      title,
      'Land',
      `{T}, Pay 1 life, Sacrifice this land: Search your library for ${types} card, put it onto the battlefield, then shuffle.`,
      [],
    );
    const plan = planLandBase({
      spells: [spell('Bear', '{G}{G}', 2, 8), spell('Bolt', '{R}', 1, 8), spell('Filler', '{2}', 2, 27)],
      commander: null,
      currentLands: [
        { land: fetchland('Wooded Foothills', 'a Mountain or Forest'), quantity: 4 },
        { land: fetchland('Bloodstained Mire', 'a Swamp or Mountain'), quantity: 4 },
        { land: customLand('Stomping Ground', 'Land — Mountain Forest', '({T}: Add {R} or {G}.)\nAs this land enters, you may pay 2 life. If you don\'t, it enters tapped.', ['R', 'G']), quantity: 3 },
        { land: customLand('Copperline Gorge', 'Land', 'This land enters tapped unless you control two or fewer other lands.\n{T}: Add {R} or {G}.', ['R', 'G']), quantity: 4 },
        { land: customLand('Mountain', 'Basic Land — Mountain', '({T}: Add {R}.)', ['R']), quantity: 1 },
        { land: customLand('Forest', 'Basic Land — Forest', '({T}: Add {G}.)', ['G']), quantity: 1 },
      ],
      options: [],
      deckColors: ['R', 'G'],
      deckSize: 60,
      maxCopies: 4,
      commanderFormat: false,
      landCountOverride: 17,
    });
    expect(plan.targets.find(t => t.color === 'G')!.current).toBe(16);
    // Every land but the Forest makes red untapped on turn one.
    expect(plan.targets.find(t => t.color === 'R')!.turnOne!.current).toBe(16);
  });

  it('lose value once there are more than two per land they can find', () => {
    const lands = (fetches: number) => [
      { land: land('Marsh Flats'), quantity: fetches },
      { land: land('Watery Grave'), quantity: 2 },
      { land: land('Island'), quantity: 22 - fetches },
    ];
    // Watery Grave is the only target: 2 targets carry 4 fetches in full.
    expect(dimir(lands(4)).targets.find(t => t.color === 'B')!.current).toBeCloseTo(2 + 4, 9);
    // Eight fetches for two targets count as four.
    expect(dimir(lands(8)).targets.find(t => t.color === 'B')!.current).toBeCloseTo(2 + 4, 9);
    expect(dimir(lands(8), { settings: { fetchesPerTarget: 3 } }).targets.find(t => t.color === 'B')!.current)
      .toBeCloseTo(2 + 6, 9);
  });

  it('are not stacked far beyond their targets by the fill', () => {
    // Four of each fetch on offer, few real duals: the plan adds real lands
    // instead of a pile of fetches.
    const plan = planLandBase({
      spells: [
        spell('Wrath', '{2}{W}{W}', 4, 8),
        spell('Counterspell', '{U}{U}', 2, 8),
        spell('Doom Blade', '{1}{B}', 2, 8),
        spell('Fatty', '{5}', 5, 12),
      ],
      commander: null,
      currentLands: [],
      options: [
        option('Flooded Strand', { available: 4 }),
        option('Marsh Flats', { available: 4 }),
        option('Hallowed Fountain', { available: 1 }),
        option('Watery Grave', { available: 1 }),
        option('Godless Shrine', { available: 1 }),
      ],
      deckColors: ['W', 'U', 'B'],
      deckSize: 60,
      maxCopies: 4,
      commanderFormat: false,
      landCountOverride: 24,
    });
    const fetches = plan.picks.filter(p => p.profile.kind === 'fetch').reduce((s, p) => s + p.quantity, 0);
    const targets = plan.picks.filter(p => p.profile.kind !== 'fetch' && p.profile.basicTypes.length > 0)
      .reduce((s, p) => s + p.quantity, 0);
    expect(fetches).toBeLessThanOrEqual(2 * targets);
  });

  it('count partly when there are fewer targets than pips', () => {
    // One Watery Grave for Counterspell's two blue pips: 0.8 each, and four
    // fetches sharing one blue target give at most two blue sources (0.5).
    const plan = dimir([
      { land: land('Marsh Flats'), quantity: 4 },
      { land: land('Watery Grave'), quantity: 1 },
      { land: land('Island'), quantity: 8 },
      { land: BASIC_SWAMP, quantity: 11 },
    ]);
    expect(current(plan, 'U')).toBeCloseTo(1 + 8 + 4 * 0.8 * 0.5, 9);
    const custom = dimir([
      { land: land('Marsh Flats'), quantity: 4 },
      { land: land('Watery Grave'), quantity: 1 },
      { land: land('Island'), quantity: 8 },
      { land: BASIC_SWAMP, quantity: 11 },
    ], { settings: { fetchPartial: 0.5 } });
    expect(current(custom, 'U')).toBeCloseTo(1 + 8 + 4 * 0.5 * 0.5, 9);
  });

  it('count nothing without targets', () => {
    const plan = dimir([
      { land: land('Marsh Flats'), quantity: 4 },
      { land: land('Island'), quantity: 10 },
      { land: BASIC_SWAMP, quantity: 10 },
    ]);
    expect(current(plan, 'U')).toBe(10);
    expect(current(plan, 'B')).toBe(14);
  });

  it('need an untapped target to count on turn one', () => {
    const plan = planLandBase({
      spells: [spell('Opt', '{U}', 1, 8), spell('Fatty', '{5}', 5, 28)],
      commander: null,
      currentLands: [
        { land: land('Marsh Flats'), quantity: 4 },
        { land: DIMIR_TAPLAND, quantity: 4 },
        { land: land('Island'), quantity: 16 },
      ],
      options: [],
      deckColors: ['U', 'B'],
      deckSize: 60,
      maxCopies: 4,
      commanderFormat: false,
      landCountOverride: 24,
    });
    const blue = plan.targets.find(t => t.color === 'U')!;
    expect(blue.turnOne!.current).toBe(16);
  });

  it('report the chance a fetch finds nothing', () => {
    expect(deadFetchChance(60, 0, 5, 14)).toBe(0);
    const early = deadFetchChance(60, 8, 5, 10);
    const late = deadFetchChance(60, 8, 5, 14);
    expect(early).toBeGreaterThan(0);
    expect(late).toBeGreaterThan(early);
    expect(late).toBeLessThan(0.2);
    const plan = dimir([], {
      landCountOverride: 24,
      options: [option('Marsh Flats', { available: 4 }), option('Watery Grave', { available: 4 })],
    });
    expect(plan.picks.some(p => p.option.land.title === 'Marsh Flats')).toBe(true);
    expect(plan.deadFetch.map(d => d.turn)).toEqual([4, 8]);
  });
});

/** A plan with only basics for the given spells. */
function simple(spells: SpellInfo[], deckColors: ('W' | 'U' | 'B' | 'R' | 'G')[], extra: Partial<LandBaseInput> = {}) {
  return planLandBase({
    spells,
    commander: null,
    currentLands: [],
    options: [],
    deckColors,
    deckSize: 60,
    maxCopies: 4,
    commanderFormat: false,
    landCountOverride: 24,
    ...extra,
  });
}

describe('gold and hybrid spells', () => {
  it('need one more source per colour and lands making either colour', () => {
    const plan = simple([spell('Terminate', '{B}{R}', 2, 8), spell('Fatty', '{5}', 5, 28)], ['B', 'R'], {
      currentLands: [{ land: land('Academy Ruins'), quantity: 6 }],
    });
    const single = sourcesNeeded(60, 24, 1, 2).sources;
    expect(plan.targets.find(t => t.color === 'B')!.target).toBe(single + 1);
    expect(plan.targets.find(t => t.color === 'R')!.target).toBe(single + 1);
    // Both pips from lands making B or R: the CC row of the table. Six
    // colourless lands leave 18 at most.
    expect(plan.unionTargets).toHaveLength(1);
    expect(plan.unionTargets[0]!.colors).toEqual(['B', 'R']);
    expect(plan.unionTargets[0]!.target).toBe(sourcesNeeded(60, 24, 2, 2).sources);
    expect(plan.unionTargets[0]!.proposed).toBe(18);
  });

  it('count hybrid pips for either colour', () => {
    const plan = simple([spell('Kitchen Finks', '{1}{G/W}{G/W}', 3, 8), spell('Fatty', '{5}', 5, 28)], ['G', 'W']);
    expect(plan.unionTargets.map(u => [u.colors, u.driver.pips])).toEqual([[['W', 'G'], 2]]);
    expect(plan.targets.every(t => t.driver == null)).toBe(true);
  });

  it('count hybrid pips as the one colour a deck plays', () => {
    const plan = simple([spell('Kitchen Finks', '{1}{G/W}{G/W}', 3, 8), spell('Fatty', '{5}', 5, 28)], ['G']);
    expect(plan.unionTargets).toEqual([]);
    expect(plan.targets[0]!.driver).toEqual({ title: 'Kitchen Finks', pips: 2, turn: 3 });
  });
});

describe('card overrides', () => {
  const immense = spell('Become Immense', '{5}{G}', 6, 4, { oracleText: 'Delve\nTarget creature gets +6/+6 until end of turn.' });
  const fatty = spell('Fatty', '{5}', 5, 28);

  it('use a realistic cost for alternate-cost spells', () => {
    // Until the deck says how it is cast, a delve spell can wait and sets no
    // target at its printed {5}{G}.
    const plain = simple([immense, fatty], ['G']);
    expect(plain.targets[0]!.driver).toBeNull();
    expect(plain.alternateCosts).toEqual([{ title: 'Become Immense', reason: 'delve' }]);
    const key = simple([immense, fatty], ['G'], { settings: { cards: { 'Become Immense': { canWait: false } } } });
    expect(key.targets[0]!.driver!.turn).toBe(6);
    const delved = simple([immense, fatty], ['G'], { settings: { cards: { 'Become Immense': { cost: '{G}' } } } });
    expect(delved.targets[0]!.driver).toEqual({ title: 'Become Immense', pips: 1, turn: 1 });
    expect(delved.avgCmc).toBeLessThan(plain.avgCmc);
    expect(delved.alternateCosts).toEqual([]);
  });

  it('move a card to a later turn without changing its cost', () => {
    const existence = spell('Tortured Existence', '{B}', 1, 4);
    const early = simple([existence, fatty], ['B']);
    expect(early.targets[0]!.turnOne).not.toBeNull();
    const late = simple([existence, fatty], ['B'], { settings: { cards: { 'Tortured Existence': { turn: 2 } } } });
    expect(late.targets[0]!.turnOne).toBeNull();
    expect(late.targets[0]!.driver).toEqual({ title: 'Tortured Existence', pips: 1, turn: 2 });
    expect(late.avgCmc).toBe(early.avgCmc);
  });

  it('leave out cards that are never cast', () => {
    const archon = spell('Archon of Cruelty', '{6}{B}{B}', 8, 2);
    const plan = simple([archon, spell('Exhume', '{1}{B}', 2, 4), fatty], ['B'], {
      settings: { cards: { 'Archon of Cruelty': { ignore: true } } },
    });
    expect(plan.targets[0]!.driver!.title).toBe('Exhume');
    expect(plan.avgCmc).toBeCloseTo((2 * 4 + 5 * 28) / 32, 9);
  });
});

describe('cards that can wait', () => {
  // Hyper Heroic style: red creatures must come down on curve, the green
  // pump spells can wait.
  const spells = [
    spell('Hero', '{R}', 1, 12, { typeLine: 'Creature — Human' }),
    spell('Pump', '{G}{G}', 2, 8),
    spell('Filler', '{3}', 3, 23),
  ];

  it('set no colour target, so the key colour gets priority', () => {
    const plain = simple(spells, ['R', 'G'], { landCountOverride: 17 });
    const waiting = simple(spells, ['R', 'G'], { landCountOverride: 17, settings: { cards: { Pump: { canWait: true } } } });
    const green = (p: ReturnType<typeof simple>) => p.targets.find(t => t.color === 'G')!;
    const red = (p: ReturnType<typeof simple>) => p.targets.find(t => t.color === 'R')!;
    expect(green(plain).driver!.title).toBe('Pump');
    expect(green(waiting).driver).toBeNull();
    expect(red(waiting).turnOne!.proposed).toBeGreaterThan(red(plain).turnOne!.proposed);
  });

  it('still count towards how much of the deck is castable', () => {
    const waiting = simple(spells, ['R', 'G'], { landCountOverride: 17, settings: { cards: { Pump: { canWait: true } } } });
    const noForests = simple([spells[0]!, spells[2]!, spell('Pump', '{G}{G}', 2, 8)], ['R'], { landCountOverride: 17 });
    expect(waiting.picks.some(p => p.option.land.title === 'Forest')).toBe(true);
    expect(noForests.picks.some(p => p.option.land.title === 'Forest')).toBe(false);
  });
});

describe('stored settings', () => {
  it('use the saved land count unless another is given', () => {
    const spells = [spell('Bolt', '{R}', 1, 4), spell('Fatty', '{5}', 5, 32)];
    expect(simple(spells, ['R'], { landCountOverride: null, settings: { landCount: 21 } }).landCount).toBe(21);
    expect(simple(spells, ['R'], { landCountOverride: 19, settings: { landCount: 21 } }).landCount).toBe(19);
    const formula = simple(spells, ['R'], { landCountOverride: null });
    expect(formula.landCount).toBe(formula.formulaLandCount);
  });

  it('store only the differences from the defaults', () => {
    expect(manaSettingsDiff({})).toBeNull();
    expect(manaSettingsDiff({ ...DEFAULT_MANA_SETTINGS })).toBeNull();
    expect(manaSettingsDiff({
      rock: { land: 0.28, source: 0.5, minMv: 3 },
      landCount: 17,
      cards: {
        'Become Immense': { cost: ' {G} ', turn: null },
        Empty: { cost: '', ignore: false },
        Pump: { canWait: true },
      },
    })).toEqual({
      rock: { source: 0.5 },
      landCount: 17,
      cards: { 'Become Immense': { cost: '{G}' }, Pump: { canWait: true } },
    });
  });

  it('read stored JSON and ignore anything broken', () => {
    expect(parseManaSettings('{"landCount":17}')).toEqual({ landCount: 17 });
    expect(parseManaSettings(null)).toEqual({});
    expect(parseManaSettings('not json')).toEqual({});
    expect(parseManaSettings('[1,2]')).toEqual({});
    // A stored partial ratio is filled in from the defaults.
    expect(resolveManaSettings(parseManaSettings('{"rock":{"source":0.5}}')).rock)
      .toEqual({ land: 0.28, source: 0.5, minMv: 3 });
  });
});

describe('sideboard', () => {
  it('counts sideboard spells only when switched on', () => {
    const main = [spell('Bolt', '{R}', 1, 4), spell('Fatty', '{5}', 5, 30)];
    const sideboard = [spell('Anger', '{R}{R}{R}', 3, 2)];
    expect(simple(main, ['R'], { sideboard }).targets[0]!.driver!.title).toBe('Bolt');
    expect(simple(main, ['R'], { sideboard, settings: { includeSideboard: true } }).targets[0]!.driver!.title).toBe('Anger');
  });
});

describe('manaValueOf / alternateCostCards', () => {
  it('reads mana values from cost strings', () => {
    expect(manaValueOf('{2}{G}{G}')).toBe(4);
    expect(manaValueOf('{X}{R}')).toBe(1);
    expect(manaValueOf('{2/W}{G/W}')).toBe(3);
    expect(manaValueOf('')).toBe(0);
  });

  it('flags X spells and alternate costs', () => {
    expect(alternateCostCards([
      spell('Fireball', '{X}{R}', 1),
      spell('Force of Will', '{3}{U}{U}', 5, 1, { oracleText: 'You may pay 1 life and exile a blue card from your hand rather than pay this spell\'s mana cost.' }),
      spell('Terminus', '{4}{W}{W}', 6, 1, { oracleText: 'Miracle {W}' }),
      spell('Bolt', '{R}', 1),
    ])).toEqual([
      { title: 'Fireball', reason: 'X spell' },
      { title: 'Force of Will', reason: 'alternative cost' },
      { title: 'Terminus', reason: 'miracle' },
    ]);
  });
});

describe('lands already in the deck', () => {
  const tundra = customLand('Tundra', 'Land — Plains Island', '({T}: Add {W} or {U}.)', ['W', 'U']);
  const karakas = customLand('Karakas', 'Legendary Land', '{T}: Add {W}.\n{T}: Return target legendary creature to its owner\'s hand.', ['W']);
  const azorius = [spell('Counterspell', '{U}{U}', 2, 8), spell('Swords', '{W}', 1, 8), spell('Fatty', '{5}', 5, 20)];

  it('can stay when another deck uses the copy or the collection lacks it', () => {
    const plan = simple(azorius, ['W', 'U'], {
      currentLands: [
        { land: tundra, quantity: 1 },
        { land: land('Hallowed Fountain'), quantity: 2 },
        { land: land('Plains'), quantity: 10 },
        { land: land('Island'), quantity: 11 },
      ],
      // The collection counts both Fountains as used by another deck, and
      // has no Tundra at all.
      options: [option('Hallowed Fountain', { available: 0, free: 0, owned: 2, usedIn: ['Other deck'] })],
    });
    const byTitle = new Map(plan.picks.map(p => [p.option.land.title, p]));
    expect(byTitle.get('Tundra')?.quantity).toBe(1);
    expect(byTitle.get('Hallowed Fountain')?.quantity).toBe(2);
    expect(plan.picks.every(p => p.missing === 0)).toBe(true);
    expect(plan.remove.map(r => r.title)).not.toContain('Tundra');
  });

  it('keep a single-colour land of the deck over a basic on a near tie', () => {
    const plan = simple(azorius, ['W', 'U'], {
      currentLands: [
        { land: karakas, quantity: 1 },
        { land: land('Plains'), quantity: 11 },
        { land: land('Island'), quantity: 12 },
      ],
    });
    expect(plan.picks.some(p => p.option.land.title === 'Karakas')).toBe(true);
  });
});

describe('minimum basics', () => {
  const esper = [
    spell('Wrath', '{2}{W}{W}', 4, 8),
    spell('Counterspell', '{U}{U}', 2, 8),
    spell('Doom Blade', '{1}{B}', 2, 8),
    spell('Fatty', '{5}', 5, 12),
  ];
  const options = [
    option('Flooded Strand', { available: 4 }),
    option('Marsh Flats', { available: 4 }),
    option('Hallowed Fountain', { available: 4 }),
    option('Watery Grave', { available: 4 }),
    option('Godless Shrine', { available: 4 }),
    option('Seachrome Coast', { available: 4 }),
  ];
  const basics = (p: ReturnType<typeof simple>) =>
    p.picks.filter(x => x.profile.kind === 'basic').reduce((s, x) => s + x.quantity, 0);

  const basicOf = (p: ReturnType<typeof simple>, title: string) =>
    p.picks.find(x => x.option.land.title === title)?.quantity ?? 0;

  it('keeps at least that many basics of each colour asked for', () => {
    // Under Blood Moon a blue spell needs an Island, however many Plains
    // there are.
    const plan = simple(esper, ['W', 'U', 'B'], {
      options,
      settings: { minBasics: { W: 1, U: 2, B: 1, R: 0, G: 0 } },
    });
    expect(basicOf(plan, 'Plains')).toBeGreaterThanOrEqual(1);
    expect(basicOf(plan, 'Island')).toBeGreaterThanOrEqual(2);
    expect(basicOf(plan, 'Swamp')).toBeGreaterThanOrEqual(1);
    expect(plan.picks.reduce((s, x) => s + x.quantity, 0)).toBe(24);
  });

  it('reads a single number as that many of each colour the deck plays', () => {
    const plan = simple(esper, ['W', 'U', 'B'], {
      options,
      settings: { minBasics: 1 as unknown as Record<'W' | 'U' | 'B' | 'R' | 'G', number> },
    });
    expect(basicOf(plan, 'Plains')).toBeGreaterThanOrEqual(1);
    expect(basicOf(plan, 'Island')).toBeGreaterThanOrEqual(1);
    expect(basicOf(plan, 'Swamp')).toBeGreaterThanOrEqual(1);
    expect(basics(plan)).toBeGreaterThanOrEqual(3);
  });

  it('is saved like the other settings', () => {
    expect(manaSettingsDiff({ minBasics: { W: 0, U: 2, B: 0, R: 0, G: 1 } })).toEqual({ minBasics: { U: 2, G: 1 } });
    expect(resolveManaSettings({}).minBasics).toEqual({ W: 0, U: 0, B: 0, R: 0, G: 0 });
    expect(resolveManaSettings(parseManaSettings('{"minBasics":{"U":2}}')).minBasics.U).toBe(2);
  });
});

describe('cardbase mode', () => {
  const azorius = [spell('Counterspell', '{U}{U}', 2, 8), spell('Wrath', '{2}{W}{W}', 4, 8), spell('Fatty', '{5}', 5, 20)];
  const tundra = customLand('Tundra', 'Land — Plains Island', '({T}: Add {W} or {U}.)', ['W', 'U']);
  const seat = customLand('Seat of the Synod', 'Artifact Land', '{T}: Add {U}.', ['U']);
  const cardbase = (o: LandOption): LandOption => ({ ...o, available: Infinity });

  it('prefers a basic over an owned single-colour land', () => {
    const plan = simple(azorius, ['W', 'U'], {
      options: [cardbase({ ...option('Island'), land: seat, free: 5, owned: 5 })],
    });
    expect(plan.picks.some(p => p.option.land.title === 'Seat of the Synod')).toBe(false);
  });

  it('suggests real duals you do not own over shocklands you do', () => {
    const plan = simple(azorius, ['W', 'U'], {
      maxCopies: 4,
      options: [
        cardbase(option('Hallowed Fountain', { free: 4, owned: 4, price: 8 })),
        cardbase({ ...option('Island'), land: tundra, free: 1, owned: 1, price: 390 }),
      ],
    });
    const byTitle = new Map(plan.picks.map(p => [p.option.land.title, p]));
    expect(byTitle.get('Tundra')?.quantity).toBe(4);
    expect(byTitle.get('Tundra')?.missing).toBe(3);
  });

  it('prefers lands the fetches can find over City of Brass', () => {
    // Bant with fetches and real duals on offer: fetchable lands make every
    // fetch better, a City of Brass makes none better and hurts every tap.
    const tropical = customLand('Tropical Island', 'Land — Forest Island', '({T}: Add {G} or {U}.)', ['G', 'U']);
    const savannah = customLand('Savannah', 'Land — Forest Plains', '({T}: Add {G} or {W}.)', ['G', 'W']);
    const plan = simple([
      spell('Wrath', '{2}{W}{W}', 4, 8),
      spell('Counterspell', '{U}{U}', 2, 8),
      spell('Growth', '{1}{G}', 2, 8),
      spell('Fatty', '{5}', 5, 34),
    ], ['W', 'U', 'G'], {
      deckSize: 80,
      landCountOverride: 22,
      options: [
        cardbase(option('City of Brass', { free: 4, owned: 4 })),
        cardbase(option('Hallowed Fountain', { free: 2, owned: 2 })),
        cardbase(option('Flooded Strand', { free: 4, owned: 4 })),
        cardbase(option('Marsh Flats', { free: 4, owned: 4 })),
        cardbase({ ...option('Island'), land: tundra, free: 1, owned: 1 }),
        cardbase({ ...option('Island'), land: tropical, free: 1, owned: 1 }),
        cardbase({ ...option('Island'), land: savannah, free: 1, owned: 1 }),
      ],
    });
    expect(plan.picks.some(p => p.option.land.title === 'City of Brass')).toBe(false);
  });

  it('marks City of Brass as hurting on every tap, unlike a painland', () => {
    expect(landProfile(land('City of Brass'), ['W', 'U'], false).painEveryTap).toBe(true);
    expect(landProfile(land('Mana Confluence'), ['W', 'U'], false).painEveryTap).toBe(true);
    expect(landProfile(land('Caves of Koilos'), ['W', 'B'], false).painEveryTap).toBe(false);
  });

  it('values the types a triome adds when the deck has domain cards', () => {
    const lounge = customLand('Xander\'s Lounge', 'Land — Island Swamp Mountain',
      '({T}: Add {U}, {B}, or {R}.)\nThis land enters tapped.\nCycling {3}', ['U', 'B', 'R']);
    const binding = spell('Leyline Binding', '{5}{W}', 6, 4, {
      oracleText: 'Flash\nDomain — This spell costs {1} less to cast for each basic land type among lands you control.',
    });
    const base = [spell('Counterspell', '{U}{U}', 2, 8), spell('Swords', '{W}', 1, 8), spell('Fatty', '{5}', 5, 16)];
    // The Lounge is already in the deck: with Leyline Binding it stays.
    const currentLands = [
      { land: lounge, quantity: 1 },
      { land: land('Plains'), quantity: 11 },
      { land: land('Island'), quantity: 12 },
    ];
    const withDomain = simple([...base, binding], ['W', 'U'], { currentLands });
    expect(withDomain.picks.some(p => p.option.land.title === 'Xander\'s Lounge')).toBe(true);
  });

  it('keeps the deck\'s own lands with upsides over buying more duals', () => {
    const archive = customLand('Meticulous Archive', 'Land — Plains Island',
      '({T}: Add {W} or {U}.)\nThis land enters tapped.\nWhen this land enters, surveil 1.', ['W', 'U']);
    const plan = simple(azorius, ['W', 'U'], {
      currentLands: [
        { land: archive, quantity: 1 },
        { land: tundra, quantity: 1 },
        { land: land('Plains'), quantity: 10 },
        { land: land('Island'), quantity: 12 },
      ],
      options: [cardbase({ ...option('Island'), land: tundra, free: 1, owned: 1 })],
    });
    expect(plan.picks.some(p => p.option.land.title === 'Meticulous Archive')).toBe(true);
  });

  it('prefers a utility land over basics beyond what each colour needs', () => {
    const karakas = customLand('Karakas', 'Legendary Land',
      '{T}: Add {W}.\n{T}: Return target legendary creature to its owner\'s hand.', ['W']);
    const plan = simple(azorius, ['W', 'U'], {
      options: [
        cardbase(option('Flooded Strand', { free: 4, owned: 4 })),
        cardbase({ ...option('Island'), land: karakas, free: 1, owned: 1 }),
      ],
      maxCopies: 1,
      settings: { minBasics: { W: 1, U: 1, B: 0, R: 0, G: 0 } },
    });
    const byTitle = new Map(plan.picks.map(p => [p.option.land.title, p.quantity]));
    expect(byTitle.get('Karakas')).toBe(1);
    // Wrath is {2}{W}{W}: two Plains to cast it under Blood Moon come first.
    expect(byTitle.get('Plains')).toBeGreaterThanOrEqual(2);
  });

  it('keeps lands the deck asks to keep', () => {
    const karakas = customLand('Karakas', 'Legendary Land',
      '{T}: Add {W}.\n{T}: Return target legendary creature to its owner\'s hand.', ['W']);
    const currentLands = [
      { land: karakas, quantity: 1 },
      { land: land('Plains'), quantity: 11 },
      { land: land('Island'), quantity: 12 },
    ];
    const plan = simple([spell('Counterspell', '{U}{U}', 2, 20), spell('Fatty', '{5}', 5, 16)], ['W', 'U'], {
      currentLands,
      settings: { keepLands: ['Karakas'] },
    });
    const kept = plan.picks.find(p => p.option.land.title === 'Karakas');
    expect(kept?.kept).toBe(true);
    expect(manaSettingsDiff({ keepLands: ['Karakas', 'Karakas'] })).toEqual({ keepLands: ['Karakas'] });
  });

  it('marks lands that do more than make mana', () => {
    expect(landProfile(land('Temple of Enlightenment'), ['W', 'U'], false).upside).toBe(true);
    expect(landProfile(land('Academy Ruins'), ['U'], false).upside).toBe(true);
    expect(landProfile(land('Hallowed Fountain'), ['W', 'U'], false).upside).toBe(false);
    expect(landProfile(land('Flooded Strand'), ['W', 'U'], false).upside).toBe(false);
  });

  it('marks shocklands', () => {
    expect(landProfile(land('Hallowed Fountain'), ['W', 'U'], false).shock).toBe(true);
    expect(landProfile(tundra, ['W', 'U'], false).shock).toBe(false);
  });
});

describe('lands with a drawback on every tap', () => {
  it('get less attractive with each one picked', () => {
    const plan = simple([
      spell('Wrath', '{2}{W}{W}', 4, 8),
      spell('Counterspell', '{U}{U}', 2, 8),
      spell('Growth', '{1}{G}', 2, 8),
      spell('Fatty', '{5}', 5, 34),
    ], ['W', 'U', 'G'], {
      deckSize: 80,
      landCountOverride: 22,
      options: [
        option('City of Brass', { available: 4 }),
        option('Mana Confluence', { available: 4 }),
        option('Forbidden Orchard', { available: 4 }),
        option('Hallowed Fountain', { available: 4 }),
      ],
    });
    const drawbacks = plan.picks.filter(p => p.profile.drawback).reduce((s, p) => s + p.quantity, 0);
    expect(drawbacks).toBeLessThan(8);
    expect(plan.picks.find(p => p.option.land.title === 'Hallowed Fountain')?.quantity).toBe(4);
  });

  it('treat Undiscovered Paradise as a last resort: it eats the land drop every turn', () => {
    const paradise = landProfile(land('Undiscovered Paradise'), ['W', 'U'], false);
    expect(paradise.heavyDrawback).toBe(true);
    expect(landProfile(land('Tarnished Citadel'), ['W', 'U'], false).heavyDrawback).toBe(true);
    expect(landProfile(land('City of Brass'), ['W', 'U'], false).heavyDrawback).toBe(false);
    const plan = simple([
      spell('Wrath', '{2}{W}{W}', 4, 8),
      spell('Counterspell', '{U}{U}', 2, 8),
      spell('Growth', '{1}{G}', 2, 8),
      spell('Fatty', '{5}', 5, 34),
    ], ['W', 'U', 'G'], {
      deckSize: 80,
      landCountOverride: 22,
      options: [option('Undiscovered Paradise', { available: 4 })],
    });
    expect(plan.picks.some(p => p.option.land.title === 'Undiscovered Paradise')).toBe(false);
  });

  it('include Forbidden Orchard', () => {
    expect(landProfile(land('Forbidden Orchard'), ['W', 'U'], false).drawback).toBe(true);
    expect(landProfile(land('City of Brass'), ['W', 'U'], false).drawback).toBe(true);
    expect(landProfile(land('Hallowed Fountain'), ['W', 'U'], false).drawback).toBe(false);
  });
});

describe('heavy pain lands', () => {
  it('are a last resort even when they fix every colour', () => {
    // Bant at 22 of 80 cards: the targets are out of reach, which is when a
    // rainbow land looks best. Three damage per tap is still too much.
    const plan = simple([
      spell('Wrath', '{2}{W}{W}', 4, 8),
      spell('Counterspell', '{U}{U}', 2, 8),
      spell('Growth', '{1}{G}', 2, 8),
      spell('Fatty', '{5}', 5, 34),
    ], ['W', 'U', 'G'], {
      deckSize: 80,
      landCountOverride: 22,
      options: [option('Tarnished Citadel', { available: 4 }), option('City of Brass', { available: 4 })],
    });
    const byTitle = new Map(plan.picks.map(p => [p.option.land.title, p.quantity]));
    expect(byTitle.has('Tarnished Citadel')).toBe(false);
    expect(byTitle.get('City of Brass')).toBe(4);
  });
});

describe('double-faced lands', () => {
  const pathway = customLand(
    'Hengegate Pathway // Mistgate Pathway',
    'Land // Land',
    '{T}: Add {W}.',
    ['W', 'U'],
  );
  const mdfc = customLand(
    'Sink into Stupor // Soporific Springs',
    'Instant // Land',
    'Return target spell or nonland permanent an opponent controls to its owner\'s hand.',
    ['U'],
  );

  it('count a Pathway for both colours', () => {
    const profile = landProfile(pathway, ['W', 'U'], false);
    expect(profile.colors).toEqual(['W', 'U']);
    expect(profile.kind).toBe('dual');
    expect(profile.turnOne).toBe(true);
  });

  it('count a Pathway as 2/3 of each colour in a three-colour deck', () => {
    const plan = simple([spell('Swords', '{W}', 1, 4), spell('Opt', '{U}', 1, 4), spell('Growth', '{G}', 1, 4), spell('Fatty', '{5}', 5, 24)],
      ['W', 'U', 'G'], { currentLands: [{ land: pathway, quantity: 3 }] });
    expect(plan.targets.find(t => t.color === 'W')!.turnOne!.current).toBeCloseTo(2, 9);
    expect(plan.targets.find(t => t.color === 'U')!.turnOne!.current).toBeCloseTo(2, 9);
    const twoColour = simple([spell('Swords', '{W}', 1, 4), spell('Opt', '{U}', 1, 4), spell('Fatty', '{5}', 5, 28)],
      ['W', 'U'], { currentLands: [{ land: pathway, quantity: 3 }] });
    expect(twoColour.targets.find(t => t.color === 'W')!.turnOne!.current).toBe(3);
  });

  it('never suggest a spell // land card as a land', () => {
    const plan = simple([spell('Counterspell', '{U}{U}', 2, 8), spell('Fatty', '{5}', 5, 28)], ['U'], {
      options: [{ ...option('Island'), land: mdfc, available: 4 }],
    });
    expect(plan.picks.map(p => p.option.land.title)).toEqual(['Island']);
  });
});

describe('two-faced costs', () => {
  it('use the front face, not both faces added up', () => {
    const plan = planLandBase({
      spells: [spell('Brazen Borrower // Petty Theft', '{1}{U}{U} // {1}{U}', 3, 4), spell('Fatty', '{5}', 5, 30)],
      commander: null,
      currentLands: [],
      options: [],
      deckColors: ['U'],
      deckSize: 60,
      maxCopies: 4,
      commanderFormat: false,
      landCountOverride: 24,
    });
    expect(plan.targets[0]!.driver).toEqual({ title: 'Brazen Borrower // Petty Theft', pips: 2, turn: 3 });
  });
});

describe('turn-one sources', () => {
  it('count fastlands but not checklands', () => {
    const plan = planLandBase({
      spells: [spell('Swords', '{W}', 1, 8), spell('Fatty', '{5}', 5, 28)],
      commander: null,
      currentLands: [
        { land: land('Seachrome Coast'), quantity: 4 },
        { land: land('Glacial Fortress'), quantity: 4 },
        { land: land('Plains'), quantity: 16 },
      ],
      options: [],
      deckColors: ['W', 'U'],
      deckSize: 60,
      maxCopies: 4,
      commanderFormat: false,
      landCountOverride: 24,
    });
    const white = plan.targets.find(t => t.color === 'W')!;
    expect(white.turnOne!.current).toBe(20);
    expect(white.current).toBe(20);
  });
});

describe('ratios', () => {
  const base = (extra: SpellInfo[], settings: LandBaseInput['settings'] = null) => planLandBase({
    spells: [spell('Fatty', '{3}{G}', 4, 8), spell('Filler', '{2}', 2, 20), ...extra],
    commander: null,
    currentLands: [{ land: customLand('Forest', 'Basic Land — Forest', '({T}: Add {G}.)', ['G']), quantity: 10 }],
    options: [],
    deckColors: ['G'],
    deckSize: 60,
    maxCopies: 4,
    commanderFormat: false,
    landCountOverride: 24,
    settings,
  });
  const fromProducers = (plan: ReturnType<typeof base>) => plan.targets.find(t => t.color === 'G')!.fromProducers;
  const rock = spell('Talisman', '{2}', 2, 4, { typeLine: 'Artifact', isManaProducer: true, producedMana: ['G'] });

  it('counts a rock as 0.75 for spells of mana value 3 or more', () => {
    expect(fromProducers(base([rock]))).toBeCloseTo(3, 9);
  });

  it('uses the deck\'s own ratios', () => {
    expect(fromProducers(base([rock], { rock: { land: 0.28, source: 0.5, minMv: 3 } }))).toBeCloseTo(2, 9);
    expect(fromProducers(base([rock], { rock: { land: 0.28, source: 0.75, minMv: 5 } }))).toBe(0);
  });

  it('counts ramp spells and ignores rituals', () => {
    // Colourless cost, so the 4-drop stays the hardest green spell.
    const growth = spell('Rampant Growth', '{2}', 2, 4, {
      typeLine: 'Sorcery',
      oracleText: 'Search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.',
    });
    const ritual = spell('Ritual', '{G}', 1, 4, { typeLine: 'Instant', isManaProducer: true, producedMana: ['G'] });
    expect(fromProducers(base([growth]))).toBeCloseTo(3, 9);
    expect(fromProducers(base([ritual]))).toBe(0);
  });

  it('counts MDFCs as 0.8 source and 0.4 land, mythic ones as 1 and 0.75', () => {
    const mdfc = (rarity: string) => spell('Smashing', '{3}{G}{G}', 5, 4, {
      typeLine: 'Sorcery // Land',
      producedMana: ['G'],
      isManaProducer: true,
      rarity,
    });
    const uncommon = base([mdfc('uncommon')]);
    expect(fromProducers(uncommon)).toBeCloseTo(3.2, 9);
    expect(uncommon.mdfcLands).toBeCloseTo(1.6, 9);
    const mythic = base([mdfc('mythic')]);
    expect(fromProducers(mythic)).toBeCloseTo(4, 9);
    expect(mythic.mdfcLands).toBeCloseTo(3, 9);
  });

  it('fills missing settings with the defaults', () => {
    const settings = resolveManaSettings({ dork: { land: 0.28, source: 1, minMv: 2 } });
    expect(settings.dork.source).toBe(1);
    expect(settings.rock).toEqual(DEFAULT_MANA_SETTINGS.rock);
    expect(settings.fetchPartial).toBe(0.8);
  });
});

describe('tapped limit', () => {
  it('stops at nine tapped lands in 60 cards', () => {
    const tapland = (title: string) => ({
      ...option('Plains'),
      land: customLand(title, 'Land', 'This land enters tapped.\n{T}: Add {W} or {U}.', ['W', 'U']),
      available: 4,
    });
    const plan = planLandBase({
      spells: [spell('Wrath', '{W}{W}', 2, 8), spell('Counterspell', '{U}{U}', 2, 8)],
      commander: null,
      currentLands: [],
      options: [tapland('Tapland A'), tapland('Tapland B'), tapland('Tapland C')],
      deckColors: ['W', 'U'],
      deckSize: 60,
      maxCopies: 4,
      commanderFormat: false,
      landCountOverride: 24,
    });
    expect(plan.tappedLimit).toBe(9);
    expect(plan.tappedProposed).toBe(9);
  });
});

describe('recommendedLandCount', () => {
  it('uses the 99-card regression', () => {
    // 31.42 + 3.13 * 3.3 - 0.28 * 7 = 39.79.
    expect(recommendedLandCount(3.3, 7, 99).count).toBe(40);
  });

  it('uses the 60-card regression', () => {
    // 19.59 + 1.9 * 2 - 0.28 * 8 = 21.15.
    expect(recommendedLandCount(2, 8, 60).count).toBe(21);
  });

  it('clamps silly inputs', () => {
    expect(recommendedLandCount(0, 60, 60).count).toBe(17);
    expect(recommendedLandCount(9, 0, 60).count).toBe(28);
  });
});

describe('solidPips', () => {
  it('counts plain pips and ignores hybrid and Phyrexian', () => {
    expect(solidPips('{1}{U}{U}', 'U')).toBe(2);
    expect(solidPips('{W/U}{U}', 'U')).toBe(1);
    expect(solidPips('{U/P}', 'U')).toBe(0);
  });
});

describe('landProfile', () => {
  const esper: ('W' | 'U' | 'B')[] = ['W', 'U', 'B'];

  it.each([
    ['Hallowed Fountain', ['W', 'U'], 'untapped', 'dual'],
    ['Glacial Fortress', ['W', 'U'], 'conditional', 'dual'],
    ['Seachrome Coast', ['W', 'U'], 'conditional', 'dual'],
    ['Temple of Enlightenment', ['W', 'U'], 'tapped', 'dual'],
    ["Raffine's Tower", ['W', 'U', 'B'], 'tapped', 'tri'],
    ['Command Tower', ['W', 'U', 'B'], 'untapped', 'rainbow'],
    ['Evolving Wilds', ['W', 'U', 'B'], 'tapped', 'fetch'],
    ['Fabled Passage', ['W', 'U', 'B'], 'conditional', 'fetch'],
    ['Prismatic Vista', ['W', 'U', 'B'], 'untapped', 'fetch'],
    ['Flooded Strand', ['W', 'U'], 'untapped', 'fetch'],
    ['Marsh Flats', ['W', 'B'], 'untapped', 'fetch'],
    ['Academy Ruins', [], 'untapped', 'utility'],
    ['Plains', ['W'], 'untapped', 'basic'],
  ])('%s', (title, colors, speed, kind) => {
    const p = landProfile(land(title), esper, true);
    expect(p.colors).toEqual(colors);
    expect(p.speed).toBe(speed);
    expect(p.kind).toBe(kind);
  });

  // Scryfall says these make every colour; the oracle text says otherwise.
  it.each([
    ['Cavern of Souls', 'utility'],
    ['Secluded Courtyard', 'utility'],
    ['Corrupted Crossroads', 'utility'],
    ['Springjack Pasture', 'utility'],
    ['Castle Doom', 'utility'],
    ["Baldur's Gate", 'utility'],
    ['Gond Gate', 'utility'],
    ['Mirrex', 'utility'],
    ['Rhystic Cave', 'utility'],
    ['Abandoned Outpost', 'mono'],
    ['Ash Barrens', 'utility'],
    ['Demolition Field', 'utility'],
    ['Aether Hub', 'utility'],
    ['The Grey Havens', 'utility'],
    ['Gemstone Caverns', 'utility'],
    ['Plaza of Heroes', 'utility'],
    ['Forgotten Monument', 'utility'],
    ['Lotus Vale', 'utility'],
    ['Rainbow Vale', 'utility'],
    ['Forbidden Orchard', 'rainbow'],
    ['Ash Barrens', 'utility'],
  ])('%s is not a real rainbow land', (title, kind) => {
    expect(landProfile(land(title), esper, true).kind).toBe(kind);
  });

  it.each(['Shimmering Grotto', 'Crystal Grotto', 'Opal Palace', 'Crystal Quarry', 'Fetid Heath'])(
    '%s is a costed filter land',
    title => {
      const p = landProfile(land(title), esper, true);
      expect(p.costed).toBe(true);
      expect(p.colors.length).toBeGreaterThan(0);
    },
  );

  it.each([
    ['Shire Terrace', 'tapped'],
    ['Grasslands', 'tapped'],
    ['Exotic Orchard', 'conditional'],
    ['Reflecting Pool', 'conditional'],
    ['Undiscovered Paradise', 'conditional'],
    ["Darigaaz's Caldera", 'conditional'],
    ['The Black Gate', 'untapped'],
    ['Thriving Heath', 'tapped'],
    ['Pinecrest Ridge', 'tapped'],
    ['Forsaken City', 'tapped'],
    ['River Delta', 'tapped'],
    ['Glimmervoid', 'conditional'],
    ['Thran Quarry', 'conditional'],
    ['Forbidden Orchard', 'conditional'],
  ])('%s enters %s', (title, speed) => {
    expect(landProfile(land(title), ['W', 'B', 'G'], true).speed).toBe(speed);
  });

  it('reads plain coloured abilities next to restricted ones', () => {
    expect(landProfile(land('Lake of the Dead'), esper, true).kind).toBe('utility');
    expect(landProfile(land('Serra\'s Sanctum'), esper, true).kind).toBe('utility');
    expect(landProfile(land('Tarnished Citadel'), esper, true).painful).toBe(true);
    expect(landProfile(land('Horizon Canopy'), ['W', 'G'], false).colors).toEqual(['W', 'G']);
  });

  it('treats Battlebond lands as untapped only in multiplayer', () => {
    expect(landProfile(land('Morphic Pool'), ['U', 'B'], true).speed).toBe('untapped');
    expect(landProfile(land('Morphic Pool'), ['U', 'B'], false).speed).toBe('tapped');
  });

  it('gives Command Tower no colours outside Commander', () => {
    expect(landProfile(land('Command Tower'), ['W', 'U'], false).colors).toEqual([]);
  });

  it('reads how much a painful land hurts per coloured tap', () => {
    expect(landProfile(land('Tarnished Citadel'), ['W', 'B'], false).painDamage).toBe(3);
    expect(landProfile(land('City of Brass'), ['W', 'B'], false).painDamage).toBe(1);
    expect(landProfile(land('Mana Confluence'), ['W', 'B'], false).painDamage).toBe(1);
    expect(landProfile(land('Caves of Koilos'), ['W', 'B'], false).painDamage).toBe(1);
    expect(landProfile(land('Hallowed Fountain'), ['W', 'U'], false).painDamage).toBe(0);
  });

  it('marks painlands', () => {
    expect(landProfile(land('Caves of Koilos'), ['W', 'B'], false).painful).toBe(true);
    expect(landProfile(land('Mana Confluence'), ['W', 'B'], false).painful).toBe(true);
    expect(landProfile(land('Hallowed Fountain'), ['W', 'U'], false).painful).toBe(false);
  });

  it('drops colours the deck does not play', () => {
    expect(landProfile(land('Hallowed Fountain'), ['U'], false).colors).toEqual(['U']);
  });
});

describe('planLandBase', () => {
  const monoBlue: LandBaseInput = {
    spells: [
      spell('Counterspell', '{U}{U}', 2, 4),
      spell('Brainstorm', '{U}', 1, 4),
      spell('Big Thing', '{4}{U}{U}', 6, 4),
    ],
    commander: null,
    currentLands: [],
    options: [option('Hallowed Fountain'), option('Watery Grave')],
    deckColors: ['U'],
    deckSize: 60,
    maxCopies: 4,
    commanderFormat: false,
    landCountOverride: 22,
  };

  it('uses only basics in a mono-coloured deck', () => {
    const plan = planLandBase(monoBlue);
    expect(plan.landCount).toBe(22);
    expect(plan.picks.map(p => [p.option.land.title, p.quantity])).toEqual([['Island', 22]]);
    expect(plan.targets[0]!.proposed).toBe(22);
  });

  it('prefers untapped duals in a two-colour deck and fills with basics', () => {
    const plan = planLandBase({
      ...monoBlue,
      spells: [
        spell('Counterspell', '{U}{U}', 2, 4),
        spell('Swords', '{W}', 1, 4),
        spell('Wrath', '{2}{W}{W}', 4, 4),
      ],
      deckColors: ['W', 'U'],
      options: [
        option('Hallowed Fountain'),
        option('Temple of Enlightenment'),
        option('Glacial Fortress'),
      ],
    });
    const byTitle = new Map(plan.picks.map(p => [p.option.land.title, p.quantity]));
    expect(byTitle.get('Hallowed Fountain')).toBe(4);
    expect(byTitle.get('Glacial Fortress')).toBe(4);
    expect(plan.picks.reduce((s, p) => s + p.quantity, 0)).toBe(22);
    // Swords is a one-drop: only untapped lands count for it, so neither
    // the checklands nor a tapped Temple do.
    const white = plan.targets.find(t => t.color === 'W')!;
    expect(white.turnOne).not.toBeNull();
    expect(white.turnOne!.proposed).toBe(4 + (byTitle.get('Plains') ?? 0));
    for (const t of plan.targets) {
      expect(t.probProposed).toBeGreaterThan(0.75);
    }
  });

  it('stops adding tapped lands once targets are met', () => {
    const plan = planLandBase({
      ...monoBlue,
      spells: [spell('Divination', '{2}{U}', 3, 4), spell('Pacifism', '{1}{W}', 2, 4), spell('Fatty', '{5}', 6, 20)],
      deckColors: ['W', 'U'],
      landCountOverride: 24,
      options: [option('Temple of Enlightenment'), option('Azorius Chancery')],
    });
    const tapped = plan.picks.filter(p => p.profile.speed === 'tapped').reduce((s, p) => s + p.quantity, 0);
    expect(tapped).toBeLessThan(8);
    for (const t of plan.targets) {
      expect(t.proposed).toBeGreaterThanOrEqual(t.target);
    }
  });

  it('respects singleton and collection availability', () => {
    const plan = planLandBase({
      ...monoBlue,
      spells: [spell('A', '{W}{W}', 2, 30), spell('B', '{B}{B}', 2, 30)],
      deckColors: ['W', 'B'],
      deckSize: 99,
      maxCopies: 1,
      commanderFormat: true,
      landCountOverride: 38,
      options: [
        option('Godless Shrine', { available: 1, free: 1, owned: 1 }),
        option('Caves of Koilos', { available: 0, free: 0, owned: 1 }),
        option('Scoured Barrens', { available: 1, free: 0, owned: 1, usedIn: ['Other deck'] }),
      ],
    });
    const byTitle = new Map(plan.picks.map(p => [p.option.land.title, p]));
    expect(byTitle.get('Godless Shrine')!.quantity).toBe(1);
    expect(byTitle.has('Caves of Koilos')).toBe(false);
    expect(byTitle.get('Scoured Barrens')!.missing).toBe(1);
    expect(plan.picks.reduce((s, p) => s + p.quantity, 0)).toBe(38);
  });

  it('keeps utility lands from the current deck and reports changes', () => {
    const plan = planLandBase({
      ...monoBlue,
      currentLands: [
        { land: land('Academy Ruins'), quantity: 1 },
        { land: land('Island'), quantity: 10 },
        { land: land('Watery Grave'), quantity: 2 },
      ],
    });
    const byTitle = new Map(plan.picks.map(p => [p.option.land.title, p]));
    expect(byTitle.get('Academy Ruins')!.kept).toBe(true);
    // In mono-blue a Watery Grave is as good as an Island, so the deck's own
    // choice stays rather than being swapped for nothing.
    expect(byTitle.get('Watery Grave')!.quantity).toBe(2);
    expect(byTitle.get('Island')!.quantity).toBe(19);
    expect(plan.add).toEqual([{ title: 'Island', quantity: 9 }]);
    expect(plan.remove).toEqual([]);
  });

  it('counts mana dorks as half a source, only for spells they speed up', () => {
    const plan = planLandBase({
      ...monoBlue,
      spells: [
        ...monoBlue.spells,
        spell('Dork', '{G}', 1, 4, { typeLine: 'Creature — Elf', isManaProducer: true, producedMana: ['G'] }),
        spell('Troll', '{1}{G}{G}', 3, 4, { typeLine: 'Creature — Troll' }),
      ],
      deckColors: ['U', 'G'],
    });
    const green = plan.targets.find(t => t.color === 'G')!;
    const forests = plan.picks.find(p => p.option.land.title === 'Forest')?.quantity ?? 0;
    expect(green.driver!.title).toBe('Troll');
    expect(green.fromProducers).toBe(2);
    expect(green.proposed).toBe(forests + 2);
    // The dork itself is a one-drop: the dorks do not help cast it.
    expect(green.turnOne!.proposed).toBe(forests);
  });

  it('prefers basics over equal owned lands in a mono-coloured deck', () => {
    const plan = planLandBase({
      ...monoBlue,
      commanderFormat: true,
      options: [
        option('Command Tower', { available: 1, free: 1, owned: 1 }),
        option('Flooded Strand', { available: 1, free: 1, owned: 1 }),
      ],
    });
    expect(plan.picks.map(p => p.option.land.title)).toEqual(['Island']);
  });

  it('meets a minor colour\'s target even when another colour has far more spells', () => {
    // Thirty blue two-drops against four Wraths: a fill that only adds up
    // castable spells starves white, though every target fits in 24 lands.
    const plan = planLandBase({
      ...monoBlue,
      spells: [spell('Mana Leak', '{1}{U}', 2, 30), spell('Wrath', '{2}{W}{W}', 4, 4), spell('Fatty', '{6}', 6, 2)],
      deckColors: ['W', 'U'],
      landCountOverride: 24,
      options: [option('Hallowed Fountain'), option('Glacial Fortress')],
    });
    for (const t of plan.targets) {
      expect(t.unreachable).toBe(false);
      expect(t.proposed).toBeGreaterThanOrEqual(t.target);
    }
  });

  it('shares an unreachable shortfall in proportion to the targets', () => {
    // Basics only: WW on turn 2 and UU on turn 2 each want about 21 of 24.
    const plan = planLandBase({
      ...monoBlue,
      spells: [spell('Wrath', '{W}{W}', 2, 4), spell('Counterspell', '{U}{U}', 2, 4)],
      deckColors: ['W', 'U'],
      landCountOverride: 24,
      options: [],
    });
    const [w, u] = plan.targets;
    expect(w!.target).toBe(u!.target);
    expect(Math.abs(w!.proposed - u!.proposed)).toBeLessThanOrEqual(1);
    expect(w!.proposed + u!.proposed).toBe(24);
  });

  it('uses tapped duals when only they can reach both targets', () => {
    // Golgari, 23 lands: about 13 black and 17 green sources fit only with
    // the tapped duals (13 + 17 = 30 colour counts in 23 slots).
    const plan = planLandBase({
      ...monoBlue,
      spells: [
        spell('Brownscale', '{1}{G}{G}', 3, 8),
        spell('Removal', '{1}{B}', 2, 8),
        spell('Filler', '{2}', 2, 21),
      ],
      deckColors: ['B', 'G'],
      landCountOverride: 23,
      options: [
        {
          ...option('Plains'),
          land: {
            title: 'Jungle Hollow',
            typeLine: 'Land',
            oracleText: 'This land enters tapped.\nWhen this land enters, you gain 1 life.\n{T}: Add {B} or {G}.',
            producedMana: ['B', 'G'],
          },
          available: 4,
        },
        {
          ...option('Plains'),
          land: {
            title: 'Golgari Rot Farm',
            typeLine: 'Land',
            oracleText: 'This land enters tapped.\nWhen this land enters, return a land you control to its owner\'s hand.\n{T}: Add {B}{G}.',
            producedMana: ['B', 'G'],
          },
          available: 4,
        },
      ],
    });
    for (const t of plan.targets) {
      expect(t.proposed).toBeGreaterThanOrEqual(t.target);
    }
  });

  it('names the spell that drives a target', () => {
    const plan = planLandBase(monoBlue);
    expect(plan.targets[0]!.driver).toEqual({ title: 'Counterspell', pips: 2, turn: 2 });
  });
});
