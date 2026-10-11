import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchDeckBuildPool,
  findCardsByName,
  importCardToDeck,
  saveWishlistItem,
  setCardQuantityInDeck,
} from '../services/drupalApi';
import { invalidateInventoryQueries } from '../services/queryCache';
import { useTheme } from '../context/ThemeContext';
import { bestPrice, formatPrice } from '../utils/prices';
import { toLandOption } from '../utils/poolAdapters';
import {
  ALL_COLORS,
  COLOR_LABEL,
  deckListAllowance,
  getOracleText,
  isHundredCardSingleton,
  isLand,
  isSingletonFormat,
  mainDeck,
  manaRequirement,
  normalizeFormat,
  scryfallFormatKey,
  type MtgColor,
} from '../utils/deckAnalysis';
import {
  planLandBase,
  type CurrentLand,
  type LandBasePlan,
  type LandKind,
  type LandOption,
  type LandPick,
  type SpellInfo,
} from '../utils/landBase';
import type { DeckCardWithCard, DeckCommander, PoolCard, PoolSource } from '../types/drupal';

interface LandBasePanelProps {
  deckId: string;
  cards: DeckCardWithCard[];
  format: string;
  commander: DeckCommander | null | undefined;
}

const KIND_LABEL: Record<LandKind, string> = {
  basic: 'Basic',
  fetch: 'Fetch',
  rainbow: 'Any colour',
  tri: 'Tri-land',
  dual: 'Dual',
  mono: 'Mono',
  utility: 'Utility',
};

const CELL: React.CSSProperties = { padding: '0.3rem 0.6rem', color: 'var(--ink)' };
const HEAD: React.CSSProperties = { ...CELL, background: 'var(--bg-2)', textAlign: 'left' };
const ROW: React.CSSProperties = { borderTop: '1px solid var(--line)' };

function pct(p: number): string {
  return `${Math.round(p * 100)}%`;
}

/**
 * Suggests a land base for the deck from the collection or the whole
 * cardbase, and can apply it or put missing lands on the wishlist.
 */
const LandBasePanel: React.FC<LandBasePanelProps> = ({ deckId, cards, format, commander }) => {
  const qc = useQueryClient();
  const { currency, usdToEur } = useTheme();
  const [source, setSource] = useState<PoolSource>('COLLECTION');
  const [includeUsed, setIncludeUsed] = useState(false);
  const [landCountInput, setLandCountInput] = useState('');
  const [requested, setRequested] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const main = useMemo(() => mainDeck(cards), [cards]);
  const commanderFormat = isHundredCardSingleton(format) && normalizeFormat(format) !== 'duel'
    && normalizeFormat(format) !== 'duel commander';

  const deckColors = useMemo<MtgColor[]>(() => {
    if (commander != null) {
      return ALL_COLORS.filter(c => commander.field_color_identity.includes(c));
    }
    const pips = manaRequirement(main);
    const demanded = ALL_COLORS.filter(c => pips[c] > 0);
    if (demanded.length > 0) {
      return demanded;
    }
    return ALL_COLORS.filter(c => main.some(dc => (dc.card.field_color_identity ?? []).includes(c)));
  }, [commander, main]);

  const legalIn = scryfallFormatKey(format);
  const pool = useQuery({
    queryKey: ['deckBuildPool', 'lands', source, legalIn, deckColors.join(''), deckId],
    queryFn: () => fetchDeckBuildPool({
      source,
      lands: true,
      legalIn,
      colorIdentity: deckColors,
      excludeDeckId: deckId,
    }),
    enabled: requested && deckColors.length > 0,
    staleTime: 5 * 60 * 1000,
  });

  const plan = useMemo<LandBasePlan | null>(() => {
    if (pool.data == null) {
      return null;
    }
    const spells: SpellInfo[] = main
      .filter(dc => !isLand(dc.card.field_type_line ?? ''))
      .map(dc => ({
        title: dc.card.title,
        typeLine: dc.card.field_type_line ?? '',
        oracleText: getOracleText(dc.card),
        cmc: dc.card.field_cmc ?? 0,
        isManaProducer: dc.card.field_is_mana_producer === true,
        power: dc.card.field_power ?? null,
        manaCost: dc.card.field_mana_cost ?? '',
        producedMana: dc.card.field_produced_mana ?? [],
        quantity: dc.quantity,
      }));

    const lands = new Map<string, CurrentLand>();
    for (const dc of main) {
      if (!isLand(dc.card.field_type_line ?? '')) {
        continue;
      }
      const existing = lands.get(dc.card.title);
      lands.set(dc.card.title, {
        land: {
          title: dc.card.title,
          typeLine: dc.card.field_type_line ?? '',
          oracleText: getOracleText(dc.card),
          producedMana: dc.card.field_produced_mana ?? [],
        },
        quantity: (existing?.quantity ?? 0) + dc.quantity,
      });
    }

    const options: LandOption[] = pool.data.map((p: PoolCard) => toLandOption(
      p,
      includeUsed,
      source === 'CARDBASE',
      bestPrice(p.card.attributes, currency, false, usdToEur),
    ));

    const allowance = deckListAllowance(format);
    const deckSize = allowance.mainHardMax
      ? allowance.mainTarget
      : Math.max(allowance.mainTarget, main.reduce((s, dc) => s + dc.quantity, 0));
    const override = Number.parseInt(landCountInput, 10);

    return planLandBase({
      spells,
      commander: commander != null
        ? {
          title: commander.title,
          typeLine: commander.field_type_line,
          oracleText: commander.field_oracle_text,
          cmc: commander.field_cmc,
          isManaProducer: false,
          manaCost: commander.field_mana_cost,
          producedMana: [],
          quantity: 1,
        }
        : null,
      currentLands: [...lands.values()],
      options,
      deckColors,
      deckSize,
      maxCopies: isSingletonFormat(format) ? 1 : 4,
      commanderFormat,
      landCountOverride: Number.isFinite(override) && override > 0 ? override : null,
    });
  }, [pool.data, main, includeUsed, source, currency, usdToEur, format, landCountInput, commander, deckColors, commanderFormat]);

  /** Printing to add for a card name: the pool printing, else any printing. */
  async function cardIdFor(title: string): Promise<string> {
    const fromPool = pool.data?.find(p => p.card.attributes.title === title);
    if (fromPool != null) {
      return fromPool.card.id;
    }
    const found = await findCardsByName(title);
    const exact = found.find(c => c.attributes.title === title) ?? found[0];
    if (exact == null) {
      throw new Error(`No printing found for ${title}`);
    }
    return exact.id;
  }

  const apply = useMutation({
    mutationFn: async (p: LandBasePlan) => {
      const landSlots = main.filter(dc => isLand(dc.card.field_type_line ?? ''));
      for (const r of p.remove) {
        let left = r.quantity;
        for (const slot of landSlots.filter(s => s.card.title === r.title)) {
          if (left <= 0) {
            break;
          }
          const take = Math.min(left, slot.quantity);
          await setCardQuantityInDeck(slot.id, slot.quantity - take, deckId, cards);
          left -= take;
        }
      }
      for (const a of p.add) {
        const slot = landSlots.find(s => s.card.title === a.title);
        // A title is either added or removed, never both, so the slot
        // quantity is still current here.
        if (slot != null) {
          await setCardQuantityInDeck(slot.id, slot.quantity + a.quantity, deckId, cards);
          continue;
        }
        await importCardToDeck(deckId, [{
          cardId: await cardIdFor(a.title),
          quantity: a.quantity,
          isSideboard: false,
          cardName: a.title,
        }]);
      }
    },
    onSuccess: async () => {
      setMessage('Land base applied.');
      await invalidateInventoryQueries(qc, { deckId });
    },
    onError: (e: unknown) => setMessage(e instanceof Error ? e.message : 'Applying failed.'),
  });

  const wish = useMutation({
    mutationFn: async (missing: LandPick[]) => {
      for (const pick of missing) {
        await saveWishlistItem({
          cardId: pick.option.cardId ?? await cardIdFor(pick.option.land.title),
          quantity: pick.missing,
          anyPrinting: true,
          deckId,
        });
      }
      return missing.length;
    },
    onSuccess: async (count: number) => {
      setMessage(`${count} land${count === 1 ? '' : 's'} added to the wishlist.`);
      await qc.invalidateQueries({ queryKey: ['wishlist'] });
    },
    onError: (e: unknown) => setMessage(e instanceof Error ? e.message : 'Adding to the wishlist failed.'),
  });

  const missing = plan?.picks.filter(p => p.missing > 0) ?? [];
  const changeCount = plan != null ? plan.add.length + plan.remove.length : 0;
  const sizeChange = plan != null
    ? plan.add.reduce((s, a) => s + a.quantity, 0) - plan.remove.reduce((s, r) => s + r.quantity, 0)
    : 0;

  function status(pick: LandPick): React.ReactNode {
    if (pick.kept) {
      return <span className="dim">Kept (utility)</span>;
    }
    if (pick.profile.kind === 'basic') {
      return <span className="dim">Basic</span>;
    }
    if (pick.missing > 0) {
      return <span style={{ color: 'var(--neg, #c00)' }}>Missing {pick.missing}</span>;
    }
    if (pick.option.usedIn.length > 0) {
      return <span>Owned, also in {pick.option.usedIn.join(', ')}</span>;
    }
    return <span>Owned</span>;
  }

  function confirmApply(p: LandBasePlan): void {
    const lines = [
      ...p.add.map(a => `+ ${a.quantity} ${a.title}`),
      ...p.remove.map(r => `- ${r.quantity} ${r.title}`),
    ];
    if (window.confirm(`Apply these land changes to the main deck?\n\n${lines.join('\n')}`)) {
      setMessage(null);
      apply.mutate(p);
    }
  }

  return (
    <section style={{ color: 'var(--ink)' }}>
      <h3 style={{ marginTop: 0 }}>Land base suggestion</h3>
      <p style={{ fontSize: '0.85rem', margin: '0 0 0.75rem' }}>
        Lands are chosen so the most demanding spell of each colour can be cast on curve about 90% of
        the time. Mana rocks and dorks count as half a source. Utility lands already in the deck are
        kept.
      </p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
        <label>
          <input
            type="radio"
            name="land-source"
            checked={source === 'COLLECTION'}
            onChange={() => setSource('COLLECTION')}
          />{' '}
          From my collection
        </label>
        <label>
          <input
            type="radio"
            name="land-source"
            checked={source === 'CARDBASE'}
            onChange={() => setSource('CARDBASE')}
          />{' '}
          From the entire cardbase
        </label>
        <label title="Off: only copies no other deck uses count as available.">
          <input type="checkbox" checked={includeUsed} onChange={e => setIncludeUsed(e.target.checked)} />{' '}
          Include cards used in other decks
        </label>
        <label>
          Lands:{' '}
          <input
            type="number"
            min={1}
            max={60}
            value={landCountInput}
            placeholder="auto"
            onChange={e => setLandCountInput(e.target.value)}
            style={{ width: '4.5rem' }}
          />
        </label>
        <button
          type="button"
          className="btn-accent"
          onClick={() => { setMessage(null); setRequested(true); void pool.refetch(); }}
          disabled={pool.isFetching || deckColors.length === 0}
        >
          {pool.isFetching ? 'Loading lands...' : plan != null ? 'Refresh' : 'Suggest lands'}
        </button>
      </div>

      {deckColors.length === 0 && (
        <p>This deck has no coloured spells yet, so there is nothing to build a land base for.</p>
      )}
      {pool.isError && (
        <p style={{ color: '#c00' }}>
          Could not load lands: {pool.error instanceof Error ? pool.error.message : 'unknown error'}
        </p>
      )}
      {message != null && <p><strong>{message}</strong></p>}

      {plan != null && (
        <>
          <p style={{ fontSize: '0.9rem' }}>
            <strong>{plan.landCount} lands</strong>
            {landCountInput === '' && (
              <span className="dim">
                {' '}({plan.landCountFormula}; avg MV {plan.avgCmc.toFixed(2)}, {plan.cheapRampDraw} cheap
                ramp/draw)
              </span>
            )}
            . The deck has {plan.currentLandCount} now.
          </p>
          <p style={{ fontSize: '0.9rem' }}>
            Coloured spells castable on curve: {pct(plan.castableCurrent)} now,{' '}
            <strong>{pct(plan.castableProposed)}</strong> with this land base.
          </p>
          {sizeChange !== 0 && (
            <p style={{ fontSize: '0.85rem' }}>
              Applying {sizeChange > 0 ? 'adds' : 'removes'} {Math.abs(sizeChange)} card
              {Math.abs(sizeChange) === 1 ? '' : 's'} in total.
              {sizeChange > 0
                ? ` Cut ${sizeChange} spell${sizeChange === 1 ? '' : 's'} to keep the deck size, or set a lower land count.`
                : ` Add ${-sizeChange} spell${sizeChange === -1 ? '' : 's'} to keep the deck size.`}
            </p>
          )}

          <table style={{ borderCollapse: 'collapse', fontSize: '0.85rem', marginBottom: '1rem' }}>
            <thead>
              <tr>
                <th style={HEAD}>Colour</th>
                <th style={HEAD}>Hardest spell</th>
                <th style={HEAD}>Sources wanted</th>
                <th style={HEAD}>Now</th>
                <th style={HEAD}>Proposed</th>
              </tr>
            </thead>
            <tbody>
              {plan.targets.map(t => (
                <tr key={t.color} style={ROW}>
                  <td style={CELL}>{COLOR_LABEL[t.color]}</td>
                  <td style={CELL}>
                    {t.driver != null
                      ? `${t.driver.title} (${t.driver.pips} pip${t.driver.pips === 1 ? '' : 's'}, turn ${t.driver.turn})`
                      : <span className="dim">none</span>}
                  </td>
                  <td style={CELL} className="tnum">
                    {t.target}
                    {t.unreachable && <span title="Not reachable with this land count."> (max)</span>}
                    {t.fromProducers > 0 && <span className="dim"> incl. {t.fromProducers} from rocks/dorks</span>}
                  </td>
                  <td style={CELL} className="tnum">{t.current} ({pct(t.probCurrent)})</td>
                  <td style={CELL} className="tnum">
                    <strong>{t.proposed}</strong> ({pct(t.probProposed)})
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <table style={{ borderCollapse: 'collapse', fontSize: '0.85rem', width: '100%', marginBottom: '1rem' }}>
            <thead>
              <tr>
                <th style={HEAD}>Land</th>
                <th style={HEAD}>Qty</th>
                <th style={HEAD}>Type</th>
                <th style={HEAD}>Status</th>
                <th style={{ ...HEAD, textAlign: 'right' }}>Price</th>
              </tr>
            </thead>
            <tbody>
              {plan.picks.map(pick => (
                <tr key={pick.option.land.title} style={ROW}>
                  <td style={CELL}>{pick.option.land.title}</td>
                  <td style={CELL} className="tnum">{pick.quantity}</td>
                  <td style={CELL}>
                    {KIND_LABEL[pick.profile.kind]}
                    {pick.profile.speed !== 'untapped' && <span className="dim">, {pick.profile.speed}</span>}
                    {pick.profile.painful && <span className="dim">, pain</span>}
                  </td>
                  <td style={CELL}>{status(pick)}</td>
                  <td style={{ ...CELL, textAlign: 'right' }} className="tnum">
                    {pick.profile.kind === 'basic' ? '' : formatPrice(pick.option.price, currency)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {changeCount === 0 ? (
            <p>The current land base already matches this suggestion.</p>
          ) : (
            <p style={{ fontSize: '0.85rem' }}>
              Changes:{' '}
              {[
                ...plan.add.map(a => `+${a.quantity} ${a.title}`),
                ...plan.remove.map(r => `-${r.quantity} ${r.title}`),
              ].join(', ')}
            </p>
          )}

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              type="button"
              className="btn-accent"
              disabled={changeCount === 0 || apply.isPending}
              onClick={() => confirmApply(plan)}
            >
              {apply.isPending ? 'Applying...' : 'Apply to deck'}
            </button>
            {missing.length > 0 && (
              <button
                type="button"
                disabled={wish.isPending}
                onClick={() => { setMessage(null); wish.mutate(missing); }}
              >
                {wish.isPending ? 'Adding...' : `Add ${missing.length} missing to wishlist`}
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
};

export default LandBasePanel;
