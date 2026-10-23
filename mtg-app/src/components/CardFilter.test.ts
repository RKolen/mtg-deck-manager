import { describe, expect, it } from 'vitest';
import { CMC_SEVEN_PLUS, cmcBounds } from './CardFilter';

describe('cmcBounds', () => {
  it('sends no bounds when the filter is Any', () => {
    expect(cmcBounds(null)).toEqual({});
  });

  it('caps the mana value for 0 to 6', () => {
    expect(cmcBounds(0)).toEqual({ cmcMax: 0 });
    expect(cmcBounds(6)).toEqual({ cmcMax: 6 });
  });

  it('treats 7+ as 7 or more, so an 8-drop is included', () => {
    expect(cmcBounds(CMC_SEVEN_PLUS)).toEqual({ cmcMin: 7 });
  });
});
