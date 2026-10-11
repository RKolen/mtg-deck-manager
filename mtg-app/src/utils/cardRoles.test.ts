import { describe, expect, it } from 'vitest';
import { cardRoles, isCheapRampOrDraw, type CardRole, type RoleCard } from './cardRoles';
import fixtures from './__fixtures__/cards.json';

const CARDS = new Map<string, RoleCard>(fixtures.map(c => [c.title, c]));

function card(title: string): RoleCard {
  const found = CARDS.get(title);
  if (found == null) {
    throw new Error(`Fixture missing: ${title}`);
  }
  return found;
}

const EXPECTED: [string, CardRole[]][] = [
  ['Sol Ring', ['ramp']],
  ['Llanowar Elves', ['ramp']],
  ['Birds of Paradise', ['ramp']],
  ['Cultivate', ['ramp']],
  ['Rampant Growth', ['ramp']],
  ['Arcane Signet', ['ramp']],
  ['Farseek', ['ramp']],
  ['Three Visits', ['ramp']],
  ['Smothering Tithe', ['ramp']],
  ['Brainstorm', ['draw']],
  ['Ponder', ['draw']],
  ['Harmonize', ['draw']],
  ['Rhystic Study', ['draw']],
  ['Phyrexian Arena', ['draw']],
  ["Night's Whisper", ['draw']],
  ['Esper Sentinel', ['draw']],
  ['Swords to Plowshares', ['removal']],
  ['Path to Exile', ['removal']],
  ['Lightning Bolt', ['removal']],
  ['Counterspell', ['removal']],
  ['Murder', ['removal']],
  ['Doom Blade', ['removal']],
  ['Beast Within', ['removal']],
  ['Chaos Warp', ['removal']],
  ['Anguished Unmaking', ['removal']],
  ['Wrath of God', ['wipe']],
  ['Damnation', ['wipe']],
  ['Blasphemous Act', ['wipe']],
  ['Toxic Deluge', ['wipe']],
  ['Craterhoof Behemoth', ['threat', 'finisher']],
  ['Grave Titan', ['threat', 'finisher']],
  ["Thassa's Oracle", ['finisher']],
  ['Serra Angel', ['threat']],
  ['Tarmogoyf', ['threat']],
  ['Goblin Guide', ['threat']],
  ['Command Tower', []],
  ['Evolving Wilds', []],
];

describe('cardRoles', () => {
  it.each(EXPECTED)('%s', (title, roles) => {
    expect(cardRoles(card(title))).toEqual(roles);
  });

  it('tags a creature with draw as both', () => {
    expect(cardRoles(card('Mulldrifter'))).toEqual(['draw', 'threat']);
  });

  it('tags modal removal that also bounces everything as removal and wipe', () => {
    expect(cardRoles(card('Cyclonic Rift'))).toEqual(['removal', 'wipe']);
  });

  it('tags planeswalkers as threats', () => {
    expect(cardRoles(card('Jace, the Mind Sculptor'))).toContain('threat');
  });
});

describe('isCheapRampOrDraw', () => {
  it('counts cheap ramp and draw', () => {
    expect(isCheapRampOrDraw(card('Sol Ring'))).toBe(true);
    expect(isCheapRampOrDraw(card('Ponder'))).toBe(true);
    expect(isCheapRampOrDraw(card('Rampant Growth'))).toBe(true);
  });

  it('ignores expensive ramp and non-ramp cheap cards', () => {
    expect(isCheapRampOrDraw(card('Cultivate'))).toBe(false);
    expect(isCheapRampOrDraw(card('Lightning Bolt'))).toBe(false);
  });
});
