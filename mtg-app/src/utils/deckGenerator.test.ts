import { describe, expect, it } from 'vitest';
import {
  eligibleCommanders,
  generateDeck,
  seededRandom,
  weightedPick,
  type GenCard,
  type GeneratorInput,
} from './deckGenerator';
import { templateById } from './deckTemplates';
import { RuleBasedFitScorer, creatureTypes, seedThemes } from './fitScore';

const TEMPLATE = templateById('commander-default');

let nextId = 0;
function card(title: string, overrides: Partial<GenCard> = {}): GenCard {
  nextId += 1;
  return {
    id: `id-${nextId}`,
    title,
    typeLine: 'Creature — Bear',
    oracleText: '',
    cmc: 2,
    isManaProducer: false,
    power: '2',
    manaCost: '{1}{G}',
    colorIdentity: ['G'],
    available: 1,
    ...overrides,
  };
}

const COMMANDER = card('Elf Lord', {
  typeLine: 'Legendary Creature — Elf Druid',
  oracleText: 'Other Elves you control get +1/+1.',
  cmc: 3,
});

/** A green pool with enough of every role. */
function pool(): GenCard[] {
  const cards: GenCard[] = [];
  for (let i = 0; i < 20; i++) {
    cards.push(card(`Ramp ${i}`, { oracleText: '{T}: Add {G}.', typeLine: 'Artifact', cmc: 2, power: null }));
    cards.push(card(`Draw ${i}`, { oracleText: 'Draw two cards.', typeLine: 'Sorcery', cmc: 3, power: null }));
    cards.push(card(`Removal ${i}`, { oracleText: 'Destroy target creature.', typeLine: 'Instant', cmc: 2, power: null }));
    cards.push(card(`Elf ${i}`, { typeLine: 'Creature — Elf Warrior', cmc: (i % 6) + 1 }));
    cards.push(card(`Bear ${i}`, { cmc: (i % 6) + 1 }));
  }
  for (let i = 0; i < 4; i++) {
    cards.push(card(`Wipe ${i}`, { oracleText: 'Destroy all creatures.', typeLine: 'Sorcery', cmc: 4, power: null }));
    cards.push(card(`Fatty ${i}`, { cmc: 7, power: '7' }));
  }
  cards.push(card('Blue Card', { colorIdentity: ['U'], manaCost: '{U}' }));
  return cards;
}

function input(overrides: Partial<GeneratorInput> = {}): GeneratorInput {
  const p = pool();
  return {
    template: TEMPLATE,
    commander: COMMANDER,
    pool: p,
    fit: new RuleBasedFitScorer().scoreSync(COMMANDER, p),
    spellCount: 62,
    chaos: 0.3,
    seed: 42,
    ...overrides,
  };
}

describe('seededRandom / weightedPick', () => {
  it('repeats for the same seed', () => {
    const a = seededRandom(7);
    const b = seededRandom(7);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });

  it('never picks zero-weight items', () => {
    const rand = seededRandom(1);
    for (let i = 0; i < 50; i++) {
      expect(weightedPick(['a', 'b'], x => (x === 'a' ? 0 : 1), rand)).toBe('b');
    }
    expect(weightedPick(['a'], () => 0, rand)).toBeNull();
  });
});

describe('fitScore', () => {
  it('reads creature types', () => {
    expect(creatureTypes('Legendary Creature — Elf Druid')).toEqual(['elf', 'druid']);
    expect(creatureTypes('Instant')).toEqual([]);
  });

  it('finds tribes and themes', () => {
    const scores = new RuleBasedFitScorer().scoreSync(COMMANDER, pool());
    expect(scores.get('Elf 1')).toBeGreaterThan(scores.get('Bear 1')!);
    expect(seedThemes({ title: 'X', typeLine: 'Creature', oracleText: 'Put a +1/+1 counter on target creature.' })
      .map(t => t.id)).toContain('counters');
  });
});

describe('generateDeck', () => {
  it('is reproducible', () => {
    const a = generateDeck(input()).cards.map(c => c.card.title);
    const b = generateDeck(input()).cards.map(c => c.card.title);
    expect(a).toEqual(b);
    const c = generateDeck(input({ seed: 43 })).cards.map(x => x.card.title);
    expect(c).not.toEqual(a);
  });

  it('fills the deck as a singleton inside the colour identity', () => {
    const deck = generateDeck(input());
    expect(deck.cards).toHaveLength(62);
    expect(new Set(deck.cards.map(c => c.card.title)).size).toBe(62);
    expect(deck.cards.some(c => c.card.title === 'Blue Card')).toBe(false);
    expect(deck.cards.some(c => c.card.title === 'Elf Lord')).toBe(false);
    expect(deck.warnings).toEqual([]);
  });

  it('meets role minimums and respects maximums', () => {
    const deck = generateDeck(input());
    for (const [role, quota] of Object.entries(TEMPLATE.roles)) {
      const count = deck.roleCounts[role as keyof typeof deck.roleCounts];
      expect(count).toBeGreaterThanOrEqual(quota!.min);
      expect(count).toBeLessThanOrEqual(quota!.max);
    }
  });

  it('prefers fitting cards at low chaos', () => {
    const elves = (chaos: number): number => {
      let total = 0;
      for (let seed = 1; seed <= 10; seed++) {
        total += generateDeck(input({ chaos, seed })).cards.filter(c => c.card.title.startsWith('Elf')).length;
      }
      return total;
    };
    expect(elves(0)).toBeGreaterThan(elves(1));
  });

  it('warns when the pool is too small', () => {
    const deck = generateDeck(input({ pool: pool().slice(0, 30) }));
    expect(deck.cards.length).toBeLessThan(62);
    expect(deck.warnings.length).toBeGreaterThan(0);
  });

  it('skips cards with no free copies', () => {
    const p = pool().map(c => (c.title.startsWith('Removal') ? { ...c, available: 0 } : c));
    const deck = generateDeck(input({ pool: p }));
    expect(deck.cards.some(c => c.card.title.startsWith('Removal'))).toBe(false);
    expect(deck.warnings.some(w => w.includes('removal'))).toBe(true);
  });
});

describe('eligibleCommanders', () => {
  it('needs enough cards in the colours and a free copy', () => {
    const p = pool();
    const blue = card('Blue Lord', { colorIdentity: ['U'], typeLine: 'Legendary Creature — Merfolk' });
    const taken = { ...COMMANDER, title: 'Taken Elf', available: 0 };
    const result = eligibleCommanders([COMMANDER, blue, taken], p, 80);
    expect(result.map(r => r.commander.title)).toEqual(['Elf Lord']);
  });
});
