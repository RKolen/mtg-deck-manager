import { describe, expect, it } from 'vitest';
import type { DeckCardWithCard, MtgCardAttributes } from '../types/drupal';
import {
  companionDeckSizeBonus,
  deckCompanion,
  deckListAllowance,
  evaluateDeckLegality,
  isMainDeckSizeOk,
} from './deckAnalysis';

const YORION_TEXT = 'Companion — Your starting deck contains at least twenty cards more than the minimum deck size. '
  + '(If this card is your chosen companion, you may put it into your hand from outside the game for {3} as a '
  + 'sorcery.)\nFlying\nWhen Yorion enters, exile any number of other nonland permanents you own and control.';
const LURRUS_TEXT = 'Companion — Each permanent card in your starting deck has mana value 2 or less.\nLifelink';

let id = 0;
function slot(title: string, quantity: number, isSideboard: boolean, oracle = '', typeLine = 'Instant'): DeckCardWithCard {
  id += 1;
  return {
    id: `slot-${id}`,
    quantity,
    isSideboard,
    isFoil: false,
    board: isSideboard ? 'side' : 'main',
    card: {
      id: `card-${id}`,
      title,
      field_type_line: typeLine,
      field_oracle_text: oracle as unknown as MtgCardAttributes['field_oracle_text'],
      field_cmc: 1,
      field_legal_formats: [],
      field_restricted_formats: [],
    } as unknown as DeckCardWithCard['card'],
  };
}

function deck(mainCount: number, side: DeckCardWithCard[]): DeckCardWithCard[] {
  return [slot('Plains', mainCount, false, '', 'Basic Land — Plains'), ...side];
}

describe('companions', () => {
  it('reads the Yorion size bonus', () => {
    expect(companionDeckSizeBonus(YORION_TEXT)).toBe(20);
    expect(companionDeckSizeBonus(LURRUS_TEXT)).toBe(0);
  });

  it('only counts a companion in the sideboard', () => {
    expect(deckCompanion(deck(60, [slot('Yorion, Sky Nomad', 1, true, YORION_TEXT)]))?.title)
      .toBe('Yorion, Sky Nomad');
    expect(deckCompanion([...deck(60, []), slot('Yorion, Sky Nomad', 1, false, YORION_TEXT)])).toBeNull();
  });

  it('raises the constructed minimum to 80 with Yorion', () => {
    const cards = deck(60, [slot('Yorion, Sky Nomad', 1, true, YORION_TEXT)]);
    const allowance = deckListAllowance('Modern', cards);
    expect(allowance.mainTarget).toBe(80);
    expect(allowance.companion).toBe('Yorion, Sky Nomad');
    expect(isMainDeckSizeOk('Modern', 60, { cards })).toBe(false);
    expect(isMainDeckSizeOk('Modern', 80, { cards: deck(80, cards.slice(1)) })).toBe(true);
    expect(evaluateDeckLegality('Modern', cards).issues[0]?.message).toContain('Yorion');
  });

  it('leaves the minimum alone for other companions and without one', () => {
    expect(deckListAllowance('Modern', deck(60, [slot('Lurrus', 1, true, LURRUS_TEXT)])).mainTarget).toBe(60);
    expect(deckListAllowance('Modern').mainTarget).toBe(60);
  });

  it('reports cards that break a companion condition', () => {
    const titan = slot('Grave Titan', 4, false, 'Deathtouch', 'Creature — Giant');
    (titan.card as { field_cmc: number }).field_cmc = 6;
    const cards = [...deck(56, [slot('Lurrus of the Dream-Den', 1, true, LURRUS_TEXT, 'Legendary Creature — Cat Nightmare')]), titan];
    const issue = evaluateDeckLegality('Modern', cards).issues.find(i => i.code === 'companion');
    expect(issue?.message).toContain('Lurrus of the Dream-Den companion');
    expect(issue?.message).toContain('Grave Titan');
  });

  it('reports Yorion as impossible in fixed-size formats', () => {
    const cards = deck(99, [slot('Yorion, Sky Nomad', 1, true, YORION_TEXT)]);
    expect(deckListAllowance('Commander', cards).mainTarget).toBe(99);
    const issues = evaluateDeckLegality('Commander', cards).issues;
    expect(issues.some(i => i.code === 'companion')).toBe(true);
  });
});
