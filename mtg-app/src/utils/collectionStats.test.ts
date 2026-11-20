import { describe, expect, it } from 'vitest';
import { bandLabel, completion, parseCutoff, percent, shareOf, sortSets } from './collectionStats';

describe('collection stats helpers', () => {
  it('labels price bands', () => {
    expect(bandLabel(0, 0.25)).toBe('< 0.25');
    expect(bandLabel(1, 5)).toBe('1 - 5');
    expect(bandLabel(100, null)).toBe('100+');
    expect(bandLabel(null, null)).toBe('no price');
  });

  it('formats shares and completion', () => {
    expect(percent(0.4472)).toBe('44.7%');
    expect(shareOf(5, 0)).toBe(0);
    expect(completion(11, 306)).toBeCloseTo(0.0359, 3);
    expect(completion(400, 306)).toBe(1);
  });

  it('parses the cutoff with a 1 fallback', () => {
    expect(parseCutoff('2,5')).toBe(2.5);
    expect(parseCutoff('')).toBe(1);
    expect(parseCutoff('-3')).toBe(1);
  });

  it('sorts sets', () => {
    const sets = [
      { setName: 'B', value: 1, copies: 9, printings: 5, setSize: 10 },
      { setName: 'A', value: 5, copies: 1, printings: 1, setSize: 100 },
    ];
    expect(sortSets(sets, 'value')[0].setName).toBe('A');
    expect(sortSets(sets, 'completion')[0].setName).toBe('B');
    expect(sortSets(sets, 'setName')[0].setName).toBe('A');
  });
});
