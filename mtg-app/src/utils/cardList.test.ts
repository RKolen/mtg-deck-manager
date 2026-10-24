import { describe, expect, it } from 'vitest';
import { formatCardList, mergeEntries, missingEntries } from './cardList';

describe('formatCardList', () => {
  it('writes "qty name" lines with the sideboard after a blank line', () => {
    expect(formatCardList(
      [{ name: 'Kasmina, Enigma Sage', quantity: 4 }, { name: 'Thassa\'s Oracle', quantity: 1 }],
      [{ name: 'Aether Gust', quantity: 4 }],
    )).toBe('4 Kasmina, Enigma Sage\n1 Thassa\'s Oracle\n\n4 Aether Gust');
  });

  it('leaves out an empty sideboard and empty main', () => {
    expect(formatCardList([{ name: 'Forest', quantity: 2 }])).toBe('2 Forest');
    expect(formatCardList([], [{ name: 'Negate', quantity: 3 }])).toBe('3 Negate');
  });

  it('keeps double-faced names whole', () => {
    expect(formatCardList([{ name: 'Barkchannel Pathway // Tidechannel Pathway', quantity: 4 }]))
      .toBe('4 Barkchannel Pathway // Tidechannel Pathway');
  });
});

describe('mergeEntries', () => {
  it('adds up printings of the same card', () => {
    expect(mergeEntries([
      { name: 'Plains', quantity: 3 },
      { name: 'Plains', quantity: 3 },
      { name: 'Island', quantity: 1 },
    ])).toEqual([{ name: 'Plains', quantity: 6 }, { name: 'Island', quantity: 1 }]);
  });
});

describe('missingEntries', () => {
  const main = [{ name: 'Mystical Dispute', quantity: 1 }, { name: 'Breeding Pool', quantity: 4 }];
  const side = [{ name: 'Mystical Dispute', quantity: 3 }, { name: 'Negate', quantity: 3 }];
  const owned = new Map([['mystical dispute', 2], ['breeding pool', 4]]);

  it('subtracts owned copies, main deck first', () => {
    expect(missingEntries(main, side, owned, false)).toEqual({
      main: [],
      side: [{ name: 'Mystical Dispute', quantity: 2 }, { name: 'Negate', quantity: 3 }],
    });
  });

  it('keeps everything when owned cards are included', () => {
    expect(missingEntries(main, side, owned, true)).toEqual({ main, side });
  });
});
