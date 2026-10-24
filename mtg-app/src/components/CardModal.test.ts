import { describe, expect, it } from 'vitest';
import { isTokenType, priceWithFallback } from './CardModal';

const priced = (eur: string | null, usd: string | null) => ({
  field_price_eur: eur,
  field_price_eur_foil: null,
  field_price_usd: usd,
  field_price_usd_foil: null,
});

describe('priceWithFallback', () => {
  it('uses the chosen currency when the printing has it', () => {
    expect(priceWithFallback(priced('0.20', '0.30'), 'EUR', false, 0.9)).toEqual({ value: 0.2, converted: false });
  });

  it('converts a USD-only price to EUR', () => {
    const result = priceWithFallback(priced(null, '0.24'), 'EUR', false, 0.9);
    expect(result.converted).toBe(true);
    expect(result.value).toBeCloseTo(0.216);
  });

  it('gives no price without a rate or any price', () => {
    expect(priceWithFallback(priced(null, '0.24'), 'EUR', false, null).value).toBeNull();
    expect(priceWithFallback(priced(null, null), 'EUR', false, 0.9).value).toBeNull();
  });
});

describe('isTokenType', () => {
  it('recognises tokens, emblems, game pieces and reminder cards', () => {
    expect(isTokenType('Token Creature — Bat')).toBe(true);
    expect(isTokenType('Emblem — Sorin')).toBe(true);
    expect(isTokenType('Card')).toBe(true);
    expect(isTokenType('Dungeon — Undercity // Card')).toBe(true);
    expect(isTokenType('Creature')).toBe(true);
  });

  it('leaves regular cards alone', () => {
    expect(isTokenType('Creature — Elf Druid')).toBe(false);
    expect(isTokenType('Artifact')).toBe(false);
    expect(isTokenType(null)).toBe(false);
  });
});
