import { describe, expect, it } from 'vitest';
import {
  castOnCurveProbability,
  landProfile,
  planLandBase,
  recommendedLandCount,
  solidPips,
  sourcesNeeded,
  type LandBaseInput,
  type LandInfo,
  type LandOption,
  type SpellInfo,
} from './landBase';
import fixtures from './__fixtures__/cards.json';

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
  // Karsten (2022), 60 cards with 24 lands, on the play: C on turn 1 = 14,
  // 1C on turn 2 = 13, 2C on turn 3 = 12, CC on turn 2 = 21. The model
  // ignores mulligans, so it may be one source off.
  it.each([
    [1, 1, 14],
    [1, 2, 13],
    [1, 3, 12],
    [2, 2, 21],
  ])('%i pip(s) on turn %i needs about %i sources in 60 cards', (pips, turn, karsten) => {
    const { sources, unreachable } = sourcesNeeded(60, 24, pips, turn);
    expect(unreachable).toBe(false);
    expect(Math.abs(sources - karsten)).toBeLessThanOrEqual(1);
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
    // 22 lands cannot reach both 90% targets, so some tapped duals are
    // worth more than a basic, and the shortfall is shared.
    expect(byTitle.get('Temple of Enlightenment')).toBeGreaterThan(0);
    expect(plan.picks.reduce((s, p) => s + p.quantity, 0)).toBe(22);
    for (const t of plan.targets) {
      expect(t.probProposed).toBeGreaterThan(0.8);
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
    expect(byTitle.get('Island')!.quantity).toBe(21);
    expect(plan.add).toEqual([{ title: 'Island', quantity: 11 }]);
    expect(plan.remove).toEqual([{ title: 'Watery Grave', quantity: 2 }]);
  });

  it('counts mana dorks as half a source', () => {
    const plan = planLandBase({
      ...monoBlue,
      spells: [
        ...monoBlue.spells,
        spell('Dork', '{G}', 1, 4, { typeLine: 'Creature', isManaProducer: true, producedMana: ['G'] }),
      ],
      deckColors: ['U', 'G'],
    });
    const green = plan.targets.find(t => t.color === 'G')!;
    const forests = plan.picks.find(p => p.option.land.title === 'Forest')?.quantity ?? 0;
    expect(green.fromProducers).toBe(2);
    expect(green.proposed).toBe(forests + 2);
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

  it('names the spell that drives a target', () => {
    const plan = planLandBase(monoBlue);
    expect(plan.targets[0]!.driver).toEqual({ title: 'Counterspell', pips: 2, turn: 2 });
  });
});
