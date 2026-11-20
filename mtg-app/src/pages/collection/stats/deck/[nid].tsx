/**
 * Deck statistics: every card with its price and whether you own it (by
 * card name, any printing), what is missing and what it costs to complete.
 */

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useQuery } from '@tanstack/react-query';
import { fetchDeckStats } from '../../../../services/drupalApi';
import { useTheme } from '../../../../context/ThemeContext';
import { Panel, Stat } from '../../../../components/design/Panel';
import {
  FilterButtons,
  StatRow,
  StatsHeader,
  bodyRow,
  cell,
  headRow,
  link,
  num,
  statTable,
} from '../../../../components/StatsBits';
import { formatPrice, priceSourceLabel } from '../../../../utils/prices';
import { slugify } from '../../../../utils/slugify';
import {
  boardLabel,
  filterDeckCards,
  percent,
  shareOf,
  sortDeckCards,
  type DeckCardSort,
  type OwnFilter,
} from '../../../../utils/collectionStats';

const STATUS_COLOR: Record<string, string> = {
  owned: 'var(--ink)',
  partial: 'var(--accent)',
  missing: 'var(--neg)',
};

const DeckStatsPage: React.FC = () => {
  const router = useRouter();
  const { currency } = useTheme();
  const nid = Number.parseInt(String(router.query.nid ?? ''), 10);
  const [filter, setFilter] = useState<OwnFilter>('all');
  const [sort, setSort] = useState<DeckCardSort>('board');

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['deckStats', nid, currency],
    queryFn: () => fetchDeckStats(nid, currency),
    enabled: Number.isFinite(nid),
  });

  const cards = useMemo(
    () => sortDeckCards(filterDeckCards(stats?.cards ?? [], filter), sort),
    [stats?.cards, filter, sort],
  );
  const price = (v: number | null | undefined): string => formatPrice(v, currency);
  const t = stats?.totals;

  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      <StatsHeader
        loading={isLoading}
        crumbs={
          <>
            <Link href="/collection" style={link}>Collection</Link> /{' '}
            <Link href="/collection/stats" style={link}>Stats</Link> / deck
          </>
        }
        title={stats?.title ?? 'Deck statistics'}
      >
        {stats != null && (
          <Link href={`/decks/${slugify(stats.title)}`} className="mono" style={{ ...link, fontSize: 12 }}>
            Open deck →
          </Link>
        )}
      </StatsHeader>

      {error != null && (
        <div className="mono" style={{ padding: 20, color: 'var(--neg)' }}>
          Could not load deck statistics: {error instanceof Error ? error.message : String(error)}
        </div>
      )}
      {!isLoading && stats === null && (
        <div className="mono" style={{ padding: 20 }}>No deck with this ID.</div>
      )}

      {stats != null && t != null && (
        <>
          <StatRow>
            <Stat label="DECK VALUE" value={price(t.value)} sub={priceSourceLabel(currency)} accent />
            <Stat
              label="OWNED"
              value={`${t.ownedCopies} / ${t.cards}`}
              sub={`${percent(shareOf(t.ownedCopies, t.cards))} of the cards`}
            />
            <Stat label="OWNED VALUE" value={price(t.ownedValue)} sub="at the deck's printings" />
            <Stat label="MISSING" value={t.missingCopies} sub="copies" />
            <Stat
              label="TO COMPLETE"
              value={price(t.costToComplete)}
              sub={t.unpricedMissing > 0 ? `cheapest printings, ${t.unpricedMissing} unpriced` : 'cheapest printings'}
            />
            <Stat label="SHARED" value={t.sharedCards} sub="cards other decks use too" />
          </StatRow>

          <div style={{ padding: 20 }}>
            <Panel
              title={`Cards (${cards.length})`}
              right={
                <span style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <FilterButtons
                    value={filter}
                    onChange={setFilter}
                    options={[
                      { id: 'all', label: 'all' },
                      { id: 'owned', label: 'owned' },
                      { id: 'missing', label: 'missing' },
                    ]}
                  />
                  <select
                    value={sort}
                    onChange={e => setSort(e.target.value as DeckCardSort)}
                    aria-label="Sort cards"
                    style={{ fontSize: 10 }}
                  >
                    <option value="board">deck order</option>
                    <option value="value">value</option>
                    <option value="toComplete">cost to complete</option>
                    <option value="name">name</option>
                  </select>
                </span>
              }
            >
              <div className="mono dim" style={{ fontSize: 10, marginBottom: 6 }}>
                Owned is matched by card name (any printing); copies used by several decks count for each deck.
              </div>
              <table className="mono tnum" style={statTable}>
                <thead>
                  <tr className="dim" style={headRow}>
                    <th style={cell}>Card</th>
                    <th style={cell} />
                    <th style={num}>Qty</th>
                    <th style={cell}>Printing</th>
                    <th style={num}>Each</th>
                    <th style={num}>Value</th>
                    <th style={num}>Owned</th>
                    <th style={num}>To complete</th>
                    <th style={num}>Other decks</th>
                  </tr>
                </thead>
                <tbody>
                  {cards.map((c, i) => (
                    <tr key={`${c.cardId}-${c.board}-${i}`} style={bodyRow}>
                      <td style={{ ...cell, whiteSpace: 'normal' }}>
                        <Link href={`/cards/${slugify(c.title)}?printing=${c.cardId}`} style={link}>
                          {c.title}
                        </Link>
                      </td>
                      <td style={cell} className="dim">
                        {boardLabel(c.board)}
                      </td>
                      <td style={num}>{c.quantity}</td>
                      <td style={cell}>
                        <span className="dim">{c.setCode.toUpperCase()} #{c.collectorNumber}</span>
                        {c.foil && <span style={{ color: 'var(--accent)', marginLeft: 6 }}>foil</span>}
                      </td>
                      <td style={num}>{price(c.unitPrice)}</td>
                      <td style={num}>{price(c.value)}</td>
                      <td style={{ ...num, color: STATUS_COLOR[c.status] }}>
                        {c.covered} / {c.quantity}
                        <span className="dim" style={{ marginLeft: 6 }} title="Copies of this name you own">
                          ({c.owned})
                        </span>
                      </td>
                      <td style={num}>{c.missing > 0 ? price(c.costToComplete) : ''}</td>
                      <td style={num}>{c.otherDecks || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
};

export default DeckStatsPage;
