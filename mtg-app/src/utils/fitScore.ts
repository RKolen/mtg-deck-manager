/**
 * How well cards fit a deck's seed card (its commander).
 *
 * The generator only depends on the FitScorer interface. RuleBasedFitScorer
 * works offline from shared mechanics and creature types; a Milvus or Ollama
 * backed scorer can replace it later without touching the generator.
 */

export interface FitCard {
  title: string;
  typeLine: string;
  oracleText: string;
}

export interface FitScorer {
  /** Short name shown in the UI, e.g. "rules". */
  readonly name: string;
  /**
   * Scores each card from 0 (no relation) to 1 (strong fit).
   *
   * @returns Scores keyed by card title.
   */
  score(seed: FitCard, cards: FitCard[]): Promise<Map<string, number>>;
}

/** Mechanics a commander can care about, and how cards show they support it. */
export interface Theme {
  id: string;
  label: string;
  /** Matches seed text that asks for the theme. */
  seed: RegExp;
  /** Matches card text that supports it. */
  card: RegExp;
}

export const THEMES: Theme[] = [
  {
    id: 'counters',
    label: '+1/+1 counters',
    seed: /\+1\/\+1 counter|proliferate/,
    card: /\+1\/\+1 counter|proliferate/,
  },
  {
    id: 'tokens',
    label: 'Tokens',
    seed: /create[^.]* tokens?|tokens? you control|populate/,
    card: /create[^.]* (?:creature )?tokens?|populate|tokens? you control/,
  },
  {
    id: 'graveyard',
    label: 'Graveyard',
    seed: /from (?:your|a) graveyard|mill|cards? in your graveyard|dies/,
    card: /from (?:your|a) graveyard|\bmill|surveil|cards? in your graveyard|flashback|unearth|escape/,
  },
  {
    id: 'sacrifice',
    label: 'Sacrifice',
    seed: /sacrifice (?:a|another)|whenever (?:a|another) creature (?:you control )?dies/,
    card: /sacrifice (?:a|another)|whenever (?:a|another) (?:creature|permanent)[^.]*dies/,
  },
  {
    id: 'lifegain',
    label: 'Life gain',
    seed: /gain(?:s)? (?:\d+ |x )?life|lifelink|whenever you gain life/,
    card: /gain(?:s)? (?:\d+ |x |that much )?life|lifelink|whenever you gain life/,
  },
  {
    id: 'spells',
    label: 'Instants and sorceries',
    seed: /instant (?:or|and) sorcery|noncreature spell|whenever you cast (?:an? )?(?:instant|sorcery|spell)/,
    card: /instant (?:or|and) sorcery|noncreature spell|whenever you cast|copy target (?:instant|sorcery)|magecraft|prowess/,
  },
  {
    id: 'artifacts',
    label: 'Artifacts',
    seed: /\bartifacts?\b/,
    card: /\bartifacts?\b|treasure|clue|food/,
  },
  {
    id: 'enchantments',
    label: 'Enchantments',
    seed: /\benchantments?\b|constellation/,
    card: /\benchantments?\b|constellation/,
  },
  {
    id: 'voltron',
    label: 'Equipment and auras',
    seed: /equip|equipped|aura|enchanted creature/,
    card: /\bequip\b|equipped creature|enchant creature|enchanted creature gets/,
  },
  {
    id: 'combat',
    label: 'Attacking',
    seed: /whenever [^.]*attacks|combat damage to a player|extra combat/,
    card: /whenever [^.]*attacks|combat damage to a player|\bhaste\b|double strike|can't be blocked/,
  },
  {
    id: 'flying',
    label: 'Flyers',
    seed: /creatures? with flying|flying creatures?/,
    card: /\bflying\b/,
  },
  {
    id: 'landfall',
    label: 'Lands',
    seed: /landfall|whenever a land enters|lands? you control|play (?:an )?additional land/,
    card: /landfall|whenever a land enters|play (?:an )?additional land|search your library for [^.]*land/,
  },
  {
    id: 'draw',
    label: 'Card draw',
    seed: /whenever you draw|draw your second card/,
    card: /\bdraw (?:a|two|three|x) cards?/,
  },
  {
    id: 'planeswalkers',
    label: 'Planeswalkers',
    seed: /planeswalker|loyalty/,
    card: /planeswalker|loyalty|proliferate/,
  },
];

/** Creature types that are too generic to count as a tribe. */
const GENERIC_TYPES = new Set(['human', 'warrior', 'wizard', 'soldier', 'cleric', 'rogue', 'shaman', 'advisor', 'citizen']);

/** Creature subtypes from a type line ("Legendary Creature — Elf Druid"). */
export function creatureTypes(typeLine: string): string[] {
  const front = typeLine.split(' // ')[0] ?? '';
  if (!/\bcreature\b/i.test(front) || !front.includes('—')) {
    return [];
  }
  return (front.split('—')[1] ?? '')
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(t => t !== '');
}

function normalized(card: FitCard): string {
  // Reminder text ("It's an artifact with ...") is not what the card is about.
  let text = card.oracleText.replace(/\([^)]*\)/g, '');
  for (const face of card.title.split(' // ')) {
    if (face.trim() !== '') {
      text = text.split(face).join('this');
    }
  }
  return text.toLowerCase();
}

/** Themes the seed card asks for. */
export function seedThemes(seed: FitCard): Theme[] {
  const text = normalized(seed);
  return THEMES.filter(t => t.seed.test(text));
}

/**
 * Tribes the seed card cares about: creature types it names in its text
 * ("Elves you control"), plus its own non-generic types when it mentions
 * creature types at all.
 */
export function seedTribes(seed: FitCard, knownTypes: Set<string>): string[] {
  const text = normalized(seed);
  const named = [...knownTypes].filter(t => {
    const plural = t.endsWith('f') ? `${t.slice(0, -1)}ves` : `${t}s`;
    return new RegExp(`\\b(?:${t}|${plural})\\b`).test(text);
  });
  if (named.length > 0) {
    return named;
  }
  if (/creature type|share a creature type/.test(text)) {
    return creatureTypes(seed.typeLine).filter(t => !GENERIC_TYPES.has(t));
  }
  return [];
}

/** Offline scorer: shared mechanics and creature types. */
export class RuleBasedFitScorer implements FitScorer {
  readonly name = 'rules';

  async score(seed: FitCard, cards: FitCard[]): Promise<Map<string, number>> {
    return this.scoreSync(seed, cards);
  }

  scoreSync(seed: FitCard, cards: FitCard[]): Map<string, number> {
    const themes = seedThemes(seed);
    const knownTypes = new Set(cards.flatMap(c => creatureTypes(c.typeLine)));
    for (const t of creatureTypes(seed.typeLine)) {
      knownTypes.add(t);
    }
    const tribes = seedTribes(seed, knownTypes);
    const result = new Map<string, number>();
    for (const card of cards) {
      const text = normalized(card);
      const matched = themes.filter(t => t.card.test(text)).length;
      let raw = matched > 0 ? 0.4 + 0.2 * (matched - 1) : 0;
      if (tribes.length > 0) {
        const types = creatureTypes(card.typeLine);
        if (types.some(t => tribes.includes(t))) {
          raw += 0.6;
        }
        else if (tribes.some(t => text.includes(t))) {
          // Tribal support cards ("Elves you control get +1/+1").
          raw += 0.4;
        }
      }
      result.set(card.title, Math.min(1, raw));
    }
    return result;
  }
}
