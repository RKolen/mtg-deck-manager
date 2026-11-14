/**
 * Plain card lists ("4 Card Name", one per line) for pasting into
 * Cardmarket's wants list or a deck import. The sideboard follows after a
 * blank line.
 */

export interface CardListEntry {
  name: string;
  quantity: number;
}

/** Sums quantities per card name, keeping the first spelling and order. */
export function mergeEntries(entries: CardListEntry[]): CardListEntry[] {
  const merged = new Map<string, CardListEntry>();
  for (const entry of entries) {
    if (entry.quantity < 1 || entry.name.trim() === '') {
      continue;
    }
    const key = entry.name.trim().toLowerCase();
    const existing = merged.get(key);
    if (existing != null) {
      existing.quantity += entry.quantity;
    } else {
      merged.set(key, { name: entry.name.trim(), quantity: entry.quantity });
    }
  }
  return [...merged.values()];
}

/** "4 Card Name" lines; the sideboard follows after a blank line. */
export function formatCardList(main: CardListEntry[], side: CardListEntry[] = []): string {
  const block = (entries: CardListEntry[]): string =>
    mergeEntries(entries).map(e => `${e.quantity} ${e.name}`).join('\n');
  const mainText = block(main);
  const sideText = block(side);
  if (sideText === '') {
    return mainText;
  }
  return mainText === '' ? sideText : `${mainText}\n\n${sideText}`;
}

/**
 * Copies still to buy: owned copies (any printing) are used up by the main
 * deck first, then the sideboard. With includeOwned the full list is kept.
 *
 * @param ownedByName
 *   Owned copies per lowercase card name.
 */
export function missingEntries(
  main: CardListEntry[],
  side: CardListEntry[],
  ownedByName: Map<string, number>,
  includeOwned: boolean,
): { main: CardListEntry[]; side: CardListEntry[] } {
  const mergedMain = mergeEntries(main);
  const mergedSide = mergeEntries(side);
  if (includeOwned) {
    return { main: mergedMain, side: mergedSide };
  }
  const left = new Map(ownedByName);
  const take = (entries: CardListEntry[]): CardListEntry[] =>
    entries
      .map(entry => {
        const key = entry.name.toLowerCase();
        const owned = left.get(key) ?? 0;
        const used = Math.min(owned, entry.quantity);
        left.set(key, owned - used);
        return { name: entry.name, quantity: entry.quantity - used };
      })
      .filter(entry => entry.quantity > 0);
  const missingMain = take(mergedMain);
  const missingSide = take(mergedSide);
  return { main: missingMain, side: missingSide };
}

/** Where a line of an imported card list belongs. */
export type CardListSection = 'main' | 'side' | 'commander';

/** One card line read back from a plain-text list. */
export interface ParsedCardLine extends CardListEntry {
  section: CardListSection;
  isFoil: boolean;
  /** Set code from "(SET) 123" suffixes (Arena, Moxfield), lowercase. */
  setCode: string | null;
  collectorNumber: string | null;
}

/** Section headers used by this app and by Arena, Moxfield and Archidekt exports. */
const SECTION_HEADERS: Record<string, CardListSection | 'skip'> = {
  deck: 'main',
  main: 'main',
  maindeck: 'main',
  mainboard: 'main',
  sideboard: 'side',
  side: 'side',
  sb: 'side',
  // A companion lives in the sideboard here.
  companion: 'side',
  commander: 'commander',
  commanders: 'commander',
  maybeboard: 'skip',
  maybe: 'skip',
  considering: 'skip',
  tokens: 'skip',
};

/** Section a header line switches to, or null when the line is not a header. */
function sectionHeader(line: string): CardListSection | 'skip' | null {
  const key = line
    .replace(/^(\/\/|#)\s*/, '')
    .replace(/\s*\(\d+\)\s*$/, '')
    .replace(/:\s*$/, '')
    .replace(/\s+/g, '')
    .toLowerCase();
  return SECTION_HEADERS[key] ?? null;
}

/**
 * Reads a plain-text card list back into lines: the inverse of
 * formatCardList(), plus the usual Arena / Moxfield / Archidekt variants.
 *
 * "4 Name" and "4x Name" lines; a bare name counts as one copy. A blank
 * line after main deck cards starts the sideboard, like the export.
 * Headers (Deck, Sideboard, Commander, ...) and "SB:" prefixes pick the
 * section explicitly; maybeboard and token sections are skipped. Trailing
 * "(SET) 123" printings, "*F*" foil markers and "[Category]" tags are
 * stripped from the name.
 */
export function parseCardList(text: string): ParsedCardLine[] {
  const lines: ParsedCardLine[] = [];
  let section: CardListSection | 'skip' = 'main';
  let mainSeen = false;

  for (const raw of text.split(/\r?\n/)) {
    let line = raw.trim();
    if (line === '') {
      // The export separates the sideboard with a blank line.
      if (section === 'main' && mainSeen) section = 'side';
      continue;
    }
    const header = sectionHeader(line);
    if (header != null) {
      section = header;
      continue;
    }
    if (/^(\/\/|#)/.test(line)) continue;

    let lineSection = section;
    const sbPrefix = /^SB:\s*/i.exec(line);
    if (sbPrefix != null) {
      lineSection = 'side';
      line = line.slice(sbPrefix[0].length);
    }
    if (lineSection === 'skip') continue;

    const qtyMatch = /^(\d+)\s*x?\s+(.+)$/i.exec(line);
    const quantity = qtyMatch != null ? parseInt(qtyMatch[1]!, 10) : 1;
    let name = qtyMatch != null ? qtyMatch[2]! : line;
    if (quantity < 1) continue;

    let isFoil = false;
    let setCode: string | null = null;
    let collectorNumber: string | null = null;
    // Strip suffixes from the end, in any order: *F* / *E*, [Tags], (SET) 123.
    for (let changed = true; changed; ) {
      changed = false;
      const finish = /\s+\*([A-Z]+)\*\s*$/i.exec(name);
      if (finish != null) {
        isFoil = isFoil || ['f', 'e'].includes(finish[1]!.toLowerCase());
        name = name.slice(0, finish.index);
        changed = true;
      }
      const tag = /\s+\[[^\]]*\]\s*$/.exec(name);
      if (tag != null) {
        name = name.slice(0, tag.index);
        changed = true;
      }
      const printing = /\s+\(([A-Za-z0-9]{2,6})\)(?:\s+([A-Za-z0-9★-]+))?\s*$/.exec(name);
      if (printing != null) {
        setCode = printing[1]!.toLowerCase();
        collectorNumber = printing[2] ?? null;
        name = name.slice(0, printing.index);
        changed = true;
      }
    }
    name = name.trim();
    if (name === '' || !/^[\p{L}\d"']/u.test(name)) continue;

    lines.push({ name, quantity, section: lineSection, isFoil, setCode, collectorNumber });
    if (lineSection === 'main') mainSeen = true;
  }
  return lines;
}

/** Total copies in a list. */
export function countCards(entries: CardListEntry[]): number {
  return entries.reduce((sum, e) => sum + e.quantity, 0);
}
