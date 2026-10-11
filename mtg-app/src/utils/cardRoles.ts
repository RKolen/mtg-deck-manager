/**
 * Rule-based card role tagging from oracle text.
 *
 * Used by the land base suggester (cheap ramp/draw lowers the land count)
 * and the random deck generator (role quotas). Pure and synchronous; no AI.
 * A card can have several roles, or none (then it only counts for synergy).
 */

export type CardRole = 'ramp' | 'draw' | 'removal' | 'wipe' | 'threat' | 'finisher';

export const CARD_ROLES: CardRole[] = ['ramp', 'draw', 'removal', 'wipe', 'threat', 'finisher'];

export const CARD_ROLE_LABEL: Record<CardRole, string> = {
  ramp: 'Ramp',
  draw: 'Card draw',
  removal: 'Removal / interaction',
  wipe: 'Board wipe',
  threat: 'Threat',
  finisher: 'Finisher',
};

/** The card fields role tagging needs. */
export interface RoleCard {
  title: string;
  typeLine: string;
  oracleText: string;
  cmc: number;
  isManaProducer: boolean;
  power?: string | null;
}

const NUMBER_WORD = '(?:a|an|one|two|three|four|five|six|seven|x|\\d+|that many)';

const RAMP_PATTERNS: RegExp[] = [
  // Rampant Growth, Cultivate, Kodama's Reach, Farseek.
  /search your library for (?:up to \w+ )?(?:a |an )?(?:basic )?(?:land|forest|plains|island|swamp|mountain)[^.]*?(?:onto the battlefield|into your hand)/,
  /search your library for (?:up to \w+ )?(?:a |an )?(?:plains|island|swamp|mountain|forest)(?:,| or)[^.]*onto the battlefield/,
  /put (?:a|up to \w+) lands? cards? from your hand onto the battlefield/,
  /you may play (?:an|two) additional lands?/,
  // Mana rocks and dorks; colourless ones are not flagged as mana producers.
  /\{t\}[^\n:]*: add \{/,
];

const DRAW_PATTERNS: RegExp[] = [
  // "draw", not "draws": "whenever an opponent draws a card" is not card draw.
  new RegExp(`\\bdraw ${NUMBER_WORD} (?:additional )?cards?\\b`),
  /\bdraw cards equal to\b/,
  /\binvestigate\b/,
  /\bconnive/,
  // Impulse draw: exile the top card(s), you may play them.
  /exile the top \w+ cards? of your library[^.]*\. (?:until|you may (?:play|cast))/,
];

const REMOVAL_PATTERNS: RegExp[] = [
  /\b(?:destroy|exile) (?:up to \w+ )?(?:another )?target (?:\w+ )*?(?:creature|artifact|enchantment|planeswalker|permanent|battle)/,
  /\bdeals? (?:\d+|x|damage equal to [^.]+?) (?:damage )?to (?:any target|target (?:creature|planeswalker|attacking|blocking))/,
  /\btarget creature (?:an opponent controls )?gets -(?:\d+|x)\/-(?:\d+|x)/,
  /\bowner of target (?:nonland )?permanent\b/,
  /\bcounter target (?:\w+ )*?spell\b/,
  /\breturn (?:up to \w+ )?target (?:nonland )?(?:creature|permanent|artifact|enchantment)[^.]*to (?:its|their) owner'?s'? hand/,
  /\btarget (?:player|opponent) sacrifices an? (?:creature|permanent)/,
  /\bfights? (?:another )?target creature/,
];

const WIPE_PATTERNS: RegExp[] = [
  /\b(?:destroy|exile) (?:all|each) (?:other )?(?:nonland )?(?:creatures|permanents|artifacts|enchantments|nonland permanents|planeswalkers|creatures and)/,
  /\bdeals? \d+ damage to each (?:other )?creature/,
  /\ball (?:other )?creatures get -(?:\d+|x)\/-(?:\d+|x)/,
  // Overload (Cyclonic Rift, Vandalblast) turns targeted removal into a wipe.
  /\boverload\b[^\n]*change "target" in its text to "each/,
  /\breturn all (?:other )?(?:nonland )?(?:creatures|permanents)[^.]*to their owners'? hands/,
  /\beach player sacrifices (?:all|\w+) (?:creatures|permanents)/,
];

const FINISHER_PATTERNS: RegExp[] = [
  /\byou win the game\b/,
  /\beach opponent loses (?:\d+|x|half)/,
  /\bcreatures you control get \+\d+\/\+\d+ and gain trample/,
  /\bextra combat\b/,
  /\bdouble strike\b.*\bcreatures you control\b/,
];

function isLandType(typeLine: string): boolean {
  // Only the front face counts, like the deck build pool.
  return /\bland\b/i.test(typeLine.split(' // ')[0] ?? typeLine);
}

/**
 * Oracle text with the card's own name replaced by "this", lower case.
 * Keeps self-references ("Llanowar Elves deals...") from matching patterns
 * meant for other cards.
 */
function normalizedOracle(card: RoleCard): string {
  let text = card.oracleText;
  for (const face of card.title.split(' // ')) {
    if (face.trim() !== '') {
      text = text.split(face).join('this');
    }
  }
  return text.toLowerCase();
}

/** Returns every role the card fills. Lands get no roles. */
export function cardRoles(card: RoleCard): CardRole[] {
  if (isLandType(card.typeLine)) {
    return [];
  }
  const text = normalizedOracle(card);
  const type = card.typeLine.toLowerCase();
  const roles = new Set<CardRole>();

  if (card.isManaProducer || RAMP_PATTERNS.some(p => p.test(text))) {
    roles.add('ramp');
  }
  if (DRAW_PATTERNS.some(p => p.test(text))) {
    roles.add('draw');
  }
  if (WIPE_PATTERNS.some(p => p.test(text))) {
    roles.add('wipe');
  }
  if (REMOVAL_PATTERNS.some(p => p.test(text))) {
    roles.add('removal');
  }

  const isCreature = /\bcreature\b/.test(type);
  const isWalker = /\bplaneswalker\b/.test(type);
  const power = parseInt(card.power ?? '', 10);
  if (FINISHER_PATTERNS.some(p => p.test(text)) || ((isCreature || isWalker) && card.cmc >= 6)) {
    roles.add('finisher');
  }
  // Creatures and planeswalkers that are not just mana dorks pressure the
  // opponent; small utility creatures with power under 2 do not count.
  if (isWalker || (isCreature && !roles.has('ramp') && (Number.isNaN(power) || power >= 2))) {
    roles.add('threat');
  }

  return CARD_ROLES.filter(r => roles.has(r));
}

/** True for ramp or card draw costing 2 or less (Karsten's land formula input). */
export function isCheapRampOrDraw(card: RoleCard): boolean {
  if (card.cmc > 2) {
    return false;
  }
  const roles = cardRoles(card);
  return roles.includes('ramp') || roles.includes('draw');
}
