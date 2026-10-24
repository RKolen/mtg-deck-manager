import { describe, expect, it } from 'vitest';
import type { DeckToken } from '../services/drupalApi';
import { tokenColorWords, tokenPrice } from './DeckTokensPanel';

function token(priceEur: number | null, priceUsd: number | null): DeckToken {
  return {
    card: null,
    name: 'Food',
    typeLine: 'Token Artifact — Food',
    power: null,
    toughness: null,
    colors: [],
    oracleText: null,
    kind: 'token',
    madeBy: ['Hot Dog Cart'],
    owned: 0,
    priceEur,
    priceUsd,
  };
}

describe('tokenColorWords', () => {
  it('names colorless and colored tokens', () => {
    expect(tokenColorWords([])).toBe('colorless');
    expect(tokenColorWords(['U'])).toBe('blue');
    expect(tokenColorWords(['W', 'B'])).toBe('white-black');
  });
});

describe('tokenPrice', () => {
  it('uses the price in the chosen currency', () => {
    expect(tokenPrice(token(0.11, 0.16), 'EUR', 0.9)).toBe(0.11);
    expect(tokenPrice(token(0.11, 0.16), 'USD', 0.9)).toBe(0.16);
  });

  it('converts the other currency when the chosen one has no price', () => {
    expect(tokenPrice(token(null, 0.2), 'EUR', 0.9)).toBeCloseTo(0.18);
  });

  it('gives no price without a rate or any price', () => {
    expect(tokenPrice(token(null, 0.2), 'EUR', null)).toBeNull();
    expect(tokenPrice(token(null, null), 'EUR', 0.9)).toBeNull();
  });
});
