/**
 * Companion deck-building conditions.
 *
 * A companion only works when the starting deck (main deck, plus the
 * commander in Commander) meets its condition. Rules are matched on the
 * condition text, not the card name, so reprints work too. Yorion's size
 * condition is handled by deckListAllowance in deckAnalysis.ts.
 *
 * Multi-face cards are judged by their front face, which is what counts in
 * the library for modal double-faced and adventure cards.
 */

/** The card fields companion checks need. */
export interface CompanionCard {
  title: string;
  typeLine: string;
  cmc: number;
  manaCost: string;
  oracleText: string;
}

export interface CompanionRule {
  id: string;
  /** Short explanation for messages, e.g. "permanents must have mana value 2 or less". */
  summary: string;
  /** Matches the companion's condition text. */
  condition: RegExp;
  /** Returns the titles of starting-deck cards that break the condition. */
  offenders: (cards: CompanionCard[]) => string[];
}

const PERMANENT_TYPES = ['artifact', 'creature', 'enchantment', 'land', 'planeswalker', 'battle'];
const CARD_TYPES = ['artifact', 'creature', 'enchantment', 'instant', 'sorcery', 'planeswalker', 'battle', 'kindred', 'tribal'];
const KAHEERA_TYPES = ['cat', 'elemental', 'nightmare', 'dinosaur', 'beast'];

/** Keyword abilities that are activated abilities (Zirda). */
const ACTIVATED_KEYWORDS = /\b(?:equip|cycling|\w+cycling|crew|level up|ninjutsu|unearth|embalm|eternalize|outlast|reconfigure|scavenge|transmute|forecast|fortify|reinforce|boast|channel|transfigure|auto|craft|station)\b/;

function front(text: string): string {
  return (text.split(' // ')[0] ?? text).trim();
}

function types(card: CompanionCard): string[] {
  const line = front(card.typeLine).toLowerCase().split('—')[0] ?? '';
  return CARD_TYPES.filter(t => new RegExp(`\\b${t}\\b`).test(line));
}

function isLand(card: CompanionCard): boolean {
  return /\bland\b/i.test(front(card.typeLine));
}

function isPermanent(card: CompanionCard): boolean {
  const line = front(card.typeLine).toLowerCase();
  return PERMANENT_TYPES.some(t => new RegExp(`\\b${t}\\b`).test(line));
}

/** Mana value of one face's cost ("{2}{R}" = 3, X = 0). */
function faceManaValue(cost: string): number {
  return (cost.match(/\{[^}]+\}/g) ?? []).reduce((sum, sym) => {
    const inner = sym.slice(1, -1).toLowerCase();
    if (/^\d+$/.test(inner)) {
      return sum + Number(inner);
    }
    return inner === 'x' ? sum : sum + 1;
  }, 0);
}

/**
 * The mana cost that counts in the library. Split cards (Fire // Ice) combine
 * both halves outside the stack; adventure, modal and transform cards use
 * the front face. Split cards are recognised by a mana value equal to the
 * sum of both halves.
 */
export function deckManaCost(card: CompanionCard): string {
  const faces = card.manaCost.split(' // ');
  if (faces.length < 2 || /adventure/i.test(card.typeLine)) {
    return faces[0] ?? '';
  }
  const total = faces.reduce((s, f) => s + faceManaValue(f), 0);
  const isSplit = total > faceManaValue(faces[0] ?? '') && Math.abs(total - card.cmc) < 0.01;
  return isSplit ? faces.join('') : (faces[0] ?? '');
}

/** True when a mana cost repeats a symbol ({R}{R}, {1}{1}, {X}{X}). */
export function hasRepeatedManaSymbol(manaCost: string): boolean {
  const symbols = (manaCost.match(/\{[^}]+\}/g) ?? []).map(s => s.toUpperCase());
  return new Set(symbols).size !== symbols.length;
}

/**
 * True when the card has an activated ability: a "cost: effect" line or an
 * activated keyword. Basic lands have intrinsic mana abilities. Reminder
 * text and quoted abilities given to other objects (Treasure) do not count.
 */
export function hasActivatedAbility(card: CompanionCard): boolean {
  // Basic land types (basics, shocklands, Triomes) give an intrinsic
  // "{T}: Add" ability that only appears as reminder text.
  if (isLand(card) && /\b(?:plains|island|swamp|mountain|forest)\b/i.test(front(card.typeLine))) {
    return true;
  }
  const text = card.oracleText
    .split('\n//\n')[0]!
    .replace(/\([^)]*\)/g, '')
    .replace(/"[^"]*"/g, '')
    .toLowerCase();
  return text.split('\n').some(line => {
    const colon = line.indexOf(':');
    // "Companion — ..." and "Landfall — ..." are not costs; costs are short
    // and contain a mana symbol, {T}, or a verb such as sacrifice.
    if (colon > 0 && colon < 80) {
      const cost = line.slice(0, colon);
      // Loyalty abilities: "+1:", "−2:", "0:".
      if (/^\s*[+−-]?\s*(?:\d+|x)\s*$/.test(cost)) {
        return true;
      }
      if (/\{[^}]+\}|\bsacrifice\b|\bdiscard\b|\bremove\b|\bexile\b|\bpay\b|\btap\b|\breturn\b/.test(cost)) {
        return true;
      }
    }
    return ACTIVATED_KEYWORDS.test(line);
  });
}

function unique(titles: string[]): string[] {
  return [...new Set(titles)];
}

export const COMPANION_RULES: CompanionRule[] = [
  {
    id: 'lurrus',
    summary: 'permanent cards must have mana value 2 or less',
    condition: /each permanent card in your starting deck has mana value 2 or less/i,
    offenders: cards => unique(cards.filter(c => isPermanent(c) && c.cmc > 2).map(c => c.title)),
  },
  {
    id: 'jegantha',
    summary: 'no card may repeat a mana symbol in its cost',
    condition: /no card in your starting deck has more than one of the same mana symbol/i,
    offenders: cards => unique(cards.filter(c => hasRepeatedManaSymbol(deckManaCost(c))).map(c => c.title)),
  },
  {
    id: 'kaheera',
    summary: 'creature cards must be Cats, Elementals, Nightmares, Dinosaurs or Beasts',
    condition: /each creature card in your starting deck is a cat, elemental, nightmare, dinosaur, or beast/i,
    offenders: cards => unique(cards.filter(c => {
      if (!types(c).includes('creature')) {
        return false;
      }
      if (/\bchangeling\b/i.test(c.oracleText)) {
        return false;
      }
      const subtypes = (front(c.typeLine).split('—')[1] ?? '').toLowerCase().split(/\s+/);
      return !KAHEERA_TYPES.some(t => subtypes.includes(t));
    }).map(c => c.title)),
  },
  {
    id: 'gyruda',
    summary: 'every card must have an even mana value',
    condition: /only cards with even mana values/i,
    offenders: cards => unique(cards.filter(c => Math.round(c.cmc) % 2 !== 0).map(c => c.title)),
  },
  {
    id: 'keruga',
    summary: 'non-land cards must have mana value 3 or greater',
    condition: /only cards with mana value 3 or greater and land cards/i,
    offenders: cards => unique(cards.filter(c => !isLand(c) && c.cmc < 3).map(c => c.title)),
  },
  {
    id: 'obosh',
    summary: 'non-land cards must have an odd mana value',
    condition: /only cards with odd mana values and land cards/i,
    offenders: cards => unique(cards.filter(c => !isLand(c) && Math.round(c.cmc) % 2 !== 1).map(c => c.title)),
  },
  {
    id: 'zirda',
    summary: 'permanent cards must have an activated ability',
    condition: /each permanent card in your starting deck has an activated ability/i,
    offenders: cards => unique(cards.filter(c => isPermanent(c) && !hasActivatedAbility(c)).map(c => c.title)),
  },
  {
    id: 'lutri',
    summary: 'non-land cards must all have different names',
    condition: /each nonland card in your starting deck has a different name/i,
    offenders: cards => {
      const counts = new Map<string, number>();
      for (const c of cards) {
        if (!isLand(c)) {
          counts.set(c.title, (counts.get(c.title) ?? 0) + 1);
        }
      }
      return [...counts].filter(([, n]) => n > 1).map(([title]) => title);
    },
  },
  {
    id: 'umori',
    summary: 'non-land cards must all share a card type',
    condition: /each nonland card in your starting deck shares a card type/i,
    offenders: cards => {
      const nonland = cards.filter(c => !isLand(c));
      if (nonland.length === 0) {
        return [];
      }
      // Pick the type most cards have; everything without it breaks the rule.
      let bestType = '';
      let bestCount = -1;
      for (const t of CARD_TYPES) {
        const n = nonland.filter(c => types(c).includes(t)).length;
        if (n > bestCount) {
          bestType = t;
          bestCount = n;
        }
      }
      return unique(nonland.filter(c => !types(c).includes(bestType)).map(c => c.title));
    },
  },
];

/** The rule for a companion's oracle text, or null (Yorion, or unknown). */
export function companionRule(oracleText: string): CompanionRule | null {
  return COMPANION_RULES.find(r => r.condition.test(oracleText)) ?? null;
}

/**
 * Cards in the starting deck that break the companion's condition.
 *
 * @param startingDeck - One entry per copy (Lutri counts copies).
 */
export function companionOffenders(companionOracle: string, startingDeck: CompanionCard[]): string[] {
  return companionRule(companionOracle)?.offenders(startingDeck) ?? [];
}
