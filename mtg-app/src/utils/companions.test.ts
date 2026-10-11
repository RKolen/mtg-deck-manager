import { describe, expect, it } from 'vitest';
import {
  companionOffenders,
  companionRule,
  deckManaCost,
  hasActivatedAbility,
  hasRepeatedManaSymbol,
  type CompanionCard,
} from './companions';
import fixtures from './__fixtures__/cards.json';

const CARDS = new Map(fixtures.map(c => [c.title, c]));

function card(title: string): CompanionCard {
  const c = CARDS.get(title);
  if (c == null) {
    throw new Error(`Fixture missing: ${title}`);
  }
  return { title: c.title, typeLine: c.typeLine, cmc: c.cmc, manaCost: c.manaCost, oracleText: c.oracleText };
}

function offenders(companion: string, deck: string[]): string[] {
  return companionOffenders(card(companion).oracleText, deck.map(card));
}

describe('companionRule', () => {
  it.each([
    ['Lurrus of the Dream-Den', 'lurrus'],
    ['Jegantha, the Wellspring', 'jegantha'],
    ['Kaheera, the Orphanguard', 'kaheera'],
    ['Gyruda, Doom of Depths', 'gyruda'],
    ['Keruga, the Macrosage', 'keruga'],
    ['Obosh, the Preypiercer', 'obosh'],
    ['Zirda, the Dawnwaker', 'zirda'],
    ['Lutri, the Spellchaser', 'lutri'],
    ['Umori, the Collector', 'umori'],
  ])('recognises %s', (title, id) => {
    expect(companionRule(card(title).oracleText)?.id).toBe(id);
  });

  it('leaves Yorion to the deck size rules', () => {
    expect(companionRule(card('Yorion, Sky Nomad').oracleText)).toBeNull();
  });
});

describe('conditions', () => {
  it('Lurrus: permanents with mana value 3+ break it, spells do not', () => {
    expect(offenders('Lurrus of the Dream-Den', ['Tarmogoyf', 'Sol Ring', 'Mutavault', 'Harmonize', 'Grave Titan']))
      .toEqual(['Grave Titan']);
  });

  it('Jegantha: repeated symbols break it, split cards count both halves', () => {
    expect(offenders('Jegantha, the Wellspring', ['Lightning Bolt', 'Counterspell', 'Walking Ballista', 'Fire // Ice',
      'Bonecrusher Giant // Stomp'])).toEqual(['Counterspell', 'Walking Ballista', 'Fire // Ice']);
  });

  it('Kaheera: only its creature types', () => {
    expect(offenders('Kaheera, the Orphanguard', ['Leonin Arbiter', 'Tarmogoyf', 'Lightning Bolt']))
      .toEqual(['Tarmogoyf']);
  });

  it('Gyruda and Obosh: even and odd mana values', () => {
    expect(offenders('Gyruda, Doom of Depths', ['Counterspell', 'Lightning Bolt', 'Plains'])).toEqual(['Lightning Bolt']);
    expect(offenders('Obosh, the Preypiercer', ['Counterspell', 'Lightning Bolt', 'Plains'])).toEqual(['Counterspell']);
  });

  it('Keruga: mana value 3 or more, lands allowed', () => {
    expect(offenders('Keruga, the Macrosage', ['Harmonize', 'Lightning Bolt', 'Island'])).toEqual(['Lightning Bolt']);
  });

  it('Zirda: permanents need an activated ability', () => {
    expect(offenders('Zirda, the Dawnwaker', [
      'Birds of Paradise', 'Mutavault', 'Hallowed Fountain', 'Plains', 'Wrenn and Six', 'Walking Ballista',
      'Tarmogoyf', 'Lightning Bolt',
    ])).toEqual(['Tarmogoyf']);
  });

  it('Lutri: no repeated non-land names', () => {
    expect(offenders('Lutri, the Spellchaser', ['Counterspell', 'Counterspell', 'Island', 'Island']))
      .toEqual(['Counterspell']);
  });

  it('Umori: non-land cards share a type', () => {
    expect(offenders('Umori, the Collector', ['Tarmogoyf', 'Grave Titan', 'Walking Ballista', 'Lightning Bolt', 'Plains']))
      .toEqual(['Lightning Bolt']);
  });
});

describe('helpers', () => {
  it('reads costs that count in the library', () => {
    expect(deckManaCost(card('Fire // Ice'))).toBe('{1}{R}{1}{U}');
    expect(deckManaCost(card('Bonecrusher Giant // Stomp'))).toBe('{2}{R}');
    expect(hasRepeatedManaSymbol('{R/G}{R/G}')).toBe(true);
    expect(hasRepeatedManaSymbol('{2}{R}{G}')).toBe(false);
  });

  it('ignores quoted and reminder abilities', () => {
    expect(hasActivatedAbility({
      title: 'Treasure Maker',
      typeLine: 'Creature — Goblin',
      cmc: 2,
      manaCost: '{1}{R}',
      oracleText: 'When this creature enters, create a Treasure token. (It\'s an artifact with "{T}, Sacrifice this artifact: Add one mana of any color.")',
    })).toBe(false);
  });
});
