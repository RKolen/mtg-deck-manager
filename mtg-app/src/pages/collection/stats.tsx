/**
 * Collection statistics: value, rarities, price bands with an adjustable
 * bulk cutoff, the most valuable cards, deck usage and per-set totals.
 * All numbers come from one GraphQL query computed in Drupal.
 */

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { fetchCollectionStats, type StatBucket } from '../../services/drupalApi';
import { useTheme } from '../../context/ThemeContext';
import { Panel, Stat } from '../../components/design/Panel';
import { formatPrice, priceSourceLabel } from '../../utils/prices';
import { slugify } from '../../utils/slugify';
import {
  bandLabel,
  completion,
  currencySymbol,
  parseCutoff,
  percent,
  shareOf,
  sortSets,
  type SetSortKey,
} from '../../utils/collectionStats';

const cell: React.CSSProperties = { padding: '3px 6px', whiteSpace: 'nowrap' };
const num: React.CSSProperties = { ...cell, textAlign: 'right' };
const link: React.CSSProperties = { color: 'var(--accent)', textDecoration: 'none' };

/** Horizontal bar showing a share of the whole. */
function Bar({ share }: { share: number }) {
  return (
    <div style={{ height: 8, background: 'var(--bg-2)', width: '100%' }}>
      <div
        style={{
          height: '100%',
          width: `${Math.max(0, Math.min(1, share)) * 100}%`,
          background: 'var(--accent)',
        }}
      />
    </div>
  );
}

const CollectionStatsPage: React.FC = () => {
  const { currency } = useTheme();
  const [includeTrade, setIncludeTrade] = useState(true);
  const [cutoffInput, setCutoffInput] = useState('1');
  const [cutoff, setCutoff] = useState(1);
  const [setSort, setSetSort] = useState<SetSortKey>('value');
  const [showAllSets, setShowAllSets] = useState(false);

  // Refetch only once typing pauses.
  useEffect(() => {
    const t = setTimeout(() => setCutoff(parseCutoff(cutoffInput)), 400);
    return () => clearTimeout(t);
  }, [cutoffInput]);

  const { data: stats, isLoading, isFetching, error } = useQuery({
    queryKey: ['collectionStats', currency, includeTrade, cutoff],
    queryFn: () => fetchCollectionStats(currency, includeTrade, cutoff),
    placeholderData: keepPreviousData,
  });

  const sets = useMemo(() => sortSets(stats?.sets ?? [], setSort), [stats?.sets, setSort]);
  const price = (v: number | null | undefined): string => formatPrice(v, currency);
  const total = stats?.totals.value ?? 0;
  const sym = currencySymbol(currency);

  const bucketRow = (label: React.ReactNode, b: StatBucket, key?: string) => (
    <tr key={key} style={{ borderBottom: '1px solid var(--line)' }}>
      <td style={cell}>{label}</td>
      <td style={num}>{b.copies}</td>
      <td style={num}>{b.printings}</td>
      <td style={num}>{price(b.value)}</td>
      <td style={num}>{percent(shareOf(b.value, total))}</td>
      <td style={{ ...cell, width: '30%', minWidth: 40 }}>
        <Bar share={shareOf(b.value, total)} />
      </td>
    </tr>
  );
  const bucketHead = (first: string) => (
    <thead>
      <tr className="dim" style={{ textAlign: 'left', borderBottom: '1px solid var(--line)' }}>
        <th style={cell}>{first}</th>
        <th style={num}>Copies</th>
        <th style={num}>Printings</th>
        <th style={num}>Value</th>
        <th style={num}>Share</th>
        <th style={cell} />
      </tr>
    </thead>
  );

  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      <div
        style={{
          padding: '20px 28px',
          borderBottom: '1px solid var(--line)',
          background: 'var(--bg-1)',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'flex-end',
          gap: 24,
        }}
      >
        <div style={{ flex: 1, minWidth: 240 }}>
          <div className="mono uc dim" style={{ fontSize: 10, marginBottom: 6 }}>
            <Link href="/collection" style={link}>Collection</Link> / stats
          </div>
          <h1 className="sans" style={{ margin: 0, fontSize: 26, fontWeight: 700 }}>
            Collection statistics
            {(isLoading || isFetching) && (
              <span className="mono dim" style={{ fontSize: 11, marginLeft: 10 }}>
                loading...
              </span>
            )}
          </h1>
        </div>
        <label className="mono" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          Bulk cutoff {sym.trim()}
          <input
            type="text"
            inputMode="decimal"
            value={cutoffInput}
            onChange={e => setCutoffInput(e.target.value)}
            aria-label="Bulk cutoff per copy"
            style={{ width: 64 }}
          />
        </label>
        <label className="mono" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <input
            type="checkbox"
            checked={includeTrade}
            onChange={e => setIncludeTrade(e.target.checked)}
          />
          Include trade copies
        </label>
      </div>

      {error != null && (
        <div className="mono" style={{ padding: 20, color: 'var(--neg)' }}>
          Could not load statistics: {error instanceof Error ? error.message : String(error)}
        </div>
      )}

      {stats != null && (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: 16,
              padding: 20,
              borderBottom: '1px solid var(--line)',
            }}
          >
            <Stat label="VALUE" value={price(stats.totals.value)} sub={priceSourceLabel(currency)} accent />
            <Stat
              label="COPIES"
              value={stats.totals.copies}
              sub={`${stats.totals.regular} regular / ${stats.totals.foil} foil`}
            />
            <Stat label="PRINTINGS" value={stats.totals.printings} sub="different printings" />
            <Stat
              label="PER COPY"
              value={price(stats.totals.average)}
              sub={`average / median ${price(stats.totals.median)}`}
            />
            <Stat
              label="TRADE"
              value={stats.totals.trade}
              sub={includeTrade ? 'copies, included' : 'copies, left out'}
            />
            <Stat label="UNPRICED" value={stats.totals.unpricedCopies} sub="copies without a price" />
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
              gap: 16,
              padding: 20,
            }}
          >
            <Panel title="By rarity">
              <table className="mono tnum" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                {bucketHead('Rarity')}
                <tbody>
                  {stats.rarities.map(r => bucketRow(<span className="uc">{r.rarity}</span>, r, r.rarity))}
                </tbody>
              </table>
            </Panel>

            <Panel title={`Price per copy (${sym.trim()})`}>
              <table className="mono tnum" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                {bucketHead('Band')}
                <tbody>
                  {stats.bands.map(b => bucketRow(bandLabel(b.min, b.max), b, `${b.min}-${b.max}`))}
                </tbody>
              </table>
            </Panel>

            <Panel title={`Valuable (${price(stats.cutoff)}+ per copy) vs bulk`}>
              <table className="mono tnum" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                {bucketHead('Part')}
                <tbody>
                  {bucketRow('valuable', stats.aboveCutoff, 'above')}
                  {bucketRow('bulk', stats.belowCutoff, 'below')}
                </tbody>
              </table>
              <div className="mono dim" style={{ fontSize: 11, marginTop: 10 }}>
                Most valuable copies:
              </div>
              <table className="mono tnum" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <tbody>
                  {stats.concentration.map(c => (
                    <tr key={c.top} style={{ borderBottom: '1px solid var(--line)' }}>
                      <td style={cell}>top {c.top}</td>
                      <td style={num}>{price(c.value)}</td>
                      <td style={num}>{percent(c.share)}</td>
                      <td style={{ ...cell, width: '45%' }}>
                        <Bar share={c.share} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>

            <Panel title="Cards in decks">
              <div style={{ display: 'flex', gap: 24, marginBottom: 10 }}>
                <Stat
                  label="IN DECKS"
                  value={stats.decks.copiesInDecks}
                  sub={`${price(stats.decks.valueInDecks)} · ${percent(shareOf(stats.decks.valueInDecks, total))}`}
                />
                <Stat
                  label="NOT IN A DECK"
                  value={stats.decks.copiesFree}
                  sub={`${price(stats.decks.valueFree)} · ${percent(shareOf(stats.decks.valueFree, total))}`}
                />
              </div>
              <div className="mono dim" style={{ fontSize: 10, marginBottom: 6 }}>
                Matched by card name, any printing. Main deck, sideboard and commanders; maybeboards not counted.
              </div>
              <div style={{ maxHeight: 260, overflow: 'auto' }}>
                <table className="mono tnum" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr className="dim" style={{ textAlign: 'left', borderBottom: '1px solid var(--line)' }}>
                      <th style={cell}>Deck</th>
                      <th style={num}>Owned</th>
                      <th style={num}>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.decks.decks.map(d => (
                      <tr key={d.title} style={{ borderBottom: '1px solid var(--line)' }}>
                        <td style={{ ...cell, whiteSpace: 'normal' }}>
                          <Link href={`/decks/${slugify(d.title)}`} style={link}>{d.title}</Link>
                        </td>
                        <td style={num}>
                          {d.owned} / {d.needed}
                        </td>
                        <td style={num}>{price(d.value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>

          <div style={{ padding: '0 20px 20px' }}>
            <Panel title="Most valuable cards (per copy)">
              <table className="mono tnum" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr className="dim" style={{ textAlign: 'left', borderBottom: '1px solid var(--line)' }}>
                    <th style={cell}>#</th>
                    <th style={cell}>Card</th>
                    <th style={cell}>Set</th>
                    <th style={cell}>Rarity</th>
                    <th style={num}>Each</th>
                    <th style={num}>Qty</th>
                    <th style={num}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.topCards.map((c, i) => (
                    <tr key={`${c.title}-${c.setCode}-${c.foil}`} style={{ borderBottom: '1px solid var(--line)' }}>
                      <td style={cell}>{i + 1}</td>
                      <td style={cell}>
                        <Link href={`/cards/${slugify(c.title)}`} style={link}>{c.title}</Link>
                        {c.foil && <span style={{ color: 'var(--accent)', marginLeft: 6 }}>foil</span>}
                      </td>
                      <td style={cell}>
                        {c.setName} <span className="dim">{c.setCode.toUpperCase()}</span>
                      </td>
                      <td style={cell} className="uc">
                        {c.rarity}
                      </td>
                      <td style={num}>{price(c.unitPrice)}</td>
                      <td style={num}>{c.quantity}</td>
                      <td style={num}>{price(c.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          </div>

          <div style={{ padding: '0 20px 20px' }}>
            <Panel
              title={`Sets (${sets.length})`}
              right={
                <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  sort
                  <select
                    value={setSort}
                    onChange={e => setSetSort(e.target.value as SetSortKey)}
                    aria-label="Sort sets"
                    style={{ fontSize: 10 }}
                  >
                    <option value="value">value</option>
                    <option value="copies">copies</option>
                    <option value="printings">printings</option>
                    <option value="completion">completion</option>
                    <option value="setName">name</option>
                  </select>
                </span>
              }
            >
              <table className="mono tnum" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr className="dim" style={{ textAlign: 'left', borderBottom: '1px solid var(--line)' }}>
                    <th style={cell}>Set</th>
                    <th style={num}>Printings</th>
                    <th style={num}>Copies</th>
                    <th style={num}>M</th>
                    <th style={num}>R</th>
                    <th style={num}>U</th>
                    <th style={num}>C</th>
                    <th style={num}>Value</th>
                    <th style={cell}>Completion</th>
                  </tr>
                </thead>
                <tbody>
                  {(showAllSets ? sets : sets.slice(0, 40)).map(s => {
                    const done = completion(s.printings, s.setSize);
                    return (
                      <tr key={s.setCode} style={{ borderBottom: '1px solid var(--line)' }}>
                        <td style={{ ...cell, whiteSpace: 'normal' }}>
                          {s.setName} <span className="dim">{s.setCode.toUpperCase()}</span>
                        </td>
                        <td style={num}>{s.printings}</td>
                        <td style={num}>{s.copies}</td>
                        <td style={num}>{s.mythic || ''}</td>
                        <td style={num}>{s.rare || ''}</td>
                        <td style={num}>{s.uncommon || ''}</td>
                        <td style={num}>{s.common || ''}</td>
                        <td style={num}>{price(s.value)}</td>
                        <td style={{ ...cell, width: 160 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div style={{ flex: 1 }}>
                              <Bar share={done} />
                            </div>
                            <span className="dim" style={{ fontSize: 10, minWidth: 92, textAlign: 'right' }}>
                              {s.printings}/{s.setSize || '?'} · {percent(done)}
                            </span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {sets.length > 40 && (
                <button type="button" onClick={() => setShowAllSets(v => !v)} style={{ marginTop: 8, fontSize: 11 }}>
                  {showAllSets ? 'Show top 40' : `Show all ${sets.length} sets`}
                </button>
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
};

export default CollectionStatsPage;
