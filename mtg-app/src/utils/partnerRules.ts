/**
 * Two-commander pairing rules, read from oracle text and type lines.
 * Mirrors Drupal\mtg_graphql\PartnerRules (the API rejects invalid pairs).
 *
 * Covers Partner, Partner with <name>, Partner—<variant>, Friends forever,
 * Choose a Background and Doctor's companion.
 */

export interface PairCard {
  title: string;
  typeLine: string;
  oracleText: string;
}

export interface PairAbilities {
  partner: boolean;
  with: string | null;
  variant: string | null;
  friends: boolean;
  chooseBackground: boolean;
  background: boolean;
  companion: boolean;
  doctor: boolean;
}

/** What a card can pair with. */
export function pairAbilities(card: PairCard): PairAbilities {
  let partner = false;
  let withName: string | null = null;
  let variant: string | null = null;
  for (const raw of card.oracleText.split(/\r?\n/)) {
    const line = raw.trim();
    const named = /^Partner with ([^(]+?)\s*(?:\(|$)/.exec(line);
    const variantMatch = /^Partner\s*[—–-]\s*([^(]+?)\s*(?:\(|$)/.exec(line);
    if (named != null) {
      withName = named[1].trim();
    } else if (variantMatch != null) {
      variant = variantMatch[1].trim();
    } else if (/^Partner\s*(?:\(|$)/.test(line)) {
      partner = true;
    }
  }
  return {
    partner,
    with: withName,
    variant,
    friends: /^Friends forever\b/m.test(card.oracleText),
    chooseBackground: /^Choose a Background\b/m.test(card.oracleText),
    background: card.typeLine.includes('Background'),
    companion: /^Doctor's companion\b/m.test(card.oracleText),
    doctor: /\bTime Lord\b.*\bDoctor\b/.test(card.typeLine),
  };
}

/** Whether a commander may have a second commander at all. */
export function allowsPartner(card: PairCard): boolean {
  const a = pairAbilities(card);
  return a.partner || a.with != null || a.variant != null || a.friends || a.chooseBackground || a.companion || a.doctor;
}

function sameName(named: string, title: string): boolean {
  const front = title.split(' // ')[0].trim().toLowerCase();
  const n = named.trim().toLowerCase();
  return n === front || n === title.trim().toLowerCase();
}

/** Whether two cards can be commanders together. */
export function canPair(first: PairCard, second: PairCard): boolean {
  if (first.title === second.title) {
    return false;
  }
  const a = pairAbilities(first);
  const b = pairAbilities(second);
  if (a.partner && b.partner) return true;
  if (a.with != null && b.with != null && sameName(a.with, second.title) && sameName(b.with, first.title)) return true;
  if (a.variant != null && a.variant === b.variant) return true;
  if (a.friends && b.friends) return true;
  if ((a.chooseBackground && b.background) || (b.chooseBackground && a.background)) return true;
  return (a.companion && b.doctor) || (b.companion && a.doctor);
}

/** What to call the second commander slot for this commander. */
export function partnerLabel(commander: PairCard): string {
  const a = pairAbilities(commander);
  if (a.chooseBackground) return 'Background';
  if (a.doctor) return "Doctor's companion";
  if (a.companion) return 'Doctor';
  if (a.with != null) return `Partner (${a.with})`;
  return 'Partner';
}
