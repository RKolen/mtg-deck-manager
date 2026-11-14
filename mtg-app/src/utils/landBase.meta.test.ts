/// <reference types="vite/client" />
/**
 * Benchmark: tournament decks are tested over and over, so the suggester
 * should leave their land bases (nearly) alone. The fixture holds the
 * MTGGoldfish top decks with their cardbase land pools; it is local only
 * (git-ignored), so the test is skipped without it.
 */
import { describe, expect, it } from 'vitest';
import { planLandBase, solidPips, type LandOption, type ManaSettings, type SpellInfo } from './landBase';

interface MetaCard extends SpellInfo {
  rarity: string;
}

interface MetaBenchmark {
  decks: { format: string; title: string; poolKey: string; cards: MetaCard[] }[];
  pools: Record<string, { title: string; typeLine: string; oracleText: string; producedMana: string[]; owned: number }[]>;
}

const files = import.meta.glob<unknown>('./__fixtures__/metaBenchmark.json', { eager: true, import: 'default' });
const benchmark = Object.values(files)[0] as MetaBenchmark | undefined;

/** Cards a deck never casts from hand, as the deck owner would set them. */
const SETTINGS: Partial<ManaSettings> = {
  cards: { 'Sneaky Snacker': { ignore: true } },
};

const isFrontLand = (typeLine: string): boolean => /\bland\b/i.test(typeLine.split(' // ')[0]!);

function swapsFor(deck: MetaBenchmark['decks'][number], pools: MetaBenchmark['pools']): number {
  const spells = deck.cards.filter(c => !isFrontLand(c.typeLine));
  const lands = deck.cards.filter(c => isFrontLand(c.typeLine));
  const colors = (['W', 'U', 'B', 'R', 'G'] as const).filter(color => spells.some(s =>
    SETTINGS.cards?.[s.title]?.ignore !== true && solidPips(s.manaCost.split(' // ')[0]!, color) > 0));
  if (colors.length === 0) {
    return 0;
  }
  const options: LandOption[] = (pools[deck.poolKey] ?? []).map(p => ({
    land: { title: p.title, typeLine: p.typeLine ?? '', oracleText: p.oracleText ?? '', producedMana: p.producedMana ?? [] },
    cardId: p.title,
    available: Infinity,
    free: p.owned ?? 0,
    owned: p.owned ?? 0,
    usedIn: [],
    price: 1,
  }));
  const plan = planLandBase({
    spells,
    commander: null,
    currentLands: lands.map(l => ({ land: l, quantity: l.quantity })),
    options,
    deckColors: [...colors],
    deckSize: deck.cards.reduce((s, c) => s + c.quantity, 0),
    maxCopies: 4,
    commanderFormat: false,
    landCountOverride: lands.reduce((s, c) => s + c.quantity, 0),
    settings: SETTINGS,
  });
  return plan.add.reduce((s, a) => s + a.quantity, 0);
}

describe.skipIf(benchmark == null)('tournament deck benchmark', () => {
  it('leaves tested land bases (nearly) alone', () => {
    const { decks, pools } = benchmark!;
    const swaps = decks.map(d => swapsFor(d, pools));
    const unchanged = swaps.filter(s => s === 0).length;
    // 2026-11: 36 of 40 decks unchanged, 7 swaps in total (from 177 when the
    // suggester rebuilt land bases from scratch). Tighten, never loosen.
    expect(unchanged).toBeGreaterThanOrEqual(36);
    expect(swaps.reduce((s, n) => s + n, 0)).toBeLessThanOrEqual(7);
  });
});
