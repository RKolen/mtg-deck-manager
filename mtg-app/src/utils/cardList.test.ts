import { describe, expect, it } from 'vitest';
import { formatCardList, mergeEntries, missingEntries, parseCardList } from './cardList';

const brief = (text: string) =>
  parseCardList(text).map(l => `${l.section}:${l.quantity}:${l.name}`);

describe('parseCardList', () => {
  it('reads back what formatCardList writes', () => {
    const text = formatCardList(
      [{ name: 'Ratchet, Field Medic // Ratchet, Rescue Racer', quantity: 1 }, { name: 'Plains', quantity: 12 }],
      [{ name: 'Aether Gust', quantity: 4 }],
    );
    expect(brief(text)).toEqual([
      'main:1:Ratchet, Field Medic // Ratchet, Rescue Racer',
      'main:12:Plains',
      'side:4:Aether Gust',
    ]);
  });

  it('reads Arena and Moxfield exports with headers, printings and foil markers', () => {
    const lines = parseCardList([
      'Commander',
      '1 Ratchet, Field Medic (BOT) 17',
      '',
      'Deck',
      '1x Sol Ring (C21) 263 *F*',
      '1 Candy Trail [Draw]',
      '',
      'Sideboard (2)',
      '2 Negate',
      'Maybeboard',
      '1 Golden Egg',
    ].join('\n'));
    expect(lines.map(l => `${l.section}:${l.quantity}:${l.name}`)).toEqual([
      'commander:1:Ratchet, Field Medic',
      'main:1:Sol Ring',
      'main:1:Candy Trail',
      'side:2:Negate',
    ]);
    expect(lines[0]).toMatchObject({ setCode: 'bot', collectorNumber: '17', isFoil: false });
    expect(lines[1]).toMatchObject({ setCode: 'c21', collectorNumber: '263', isFoil: true });
  });

  it('handles SB: prefixes, bare names, comments and Windows line endings', () => {
    expect(brief('// My deck\r\n4 Lightning Bolt\r\nSB: 2 Pyroblast\r\nCounterspell\r\n')).toEqual([
      'main:4:Lightning Bolt',
      'side:2:Pyroblast',
      'main:1:Counterspell',
    ]);
  });

  it('does not start the sideboard on leading blank lines', () => {
    expect(brief('\n\n4 Island\n\n2 Negate')).toEqual(['main:4:Island', 'side:2:Negate']);
  });
});

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
