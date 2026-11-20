/**
 * Set statistics: every printing of a set with the copies you own, prices,
 * completion per rarity and the cost of the printings you are missing.
 */

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useQuery } from '@tanstack/react-query';
import { fetchSetStats } from '../../../../services/drupalApi';
import { useTheme } from '../../../../context/ThemeContext';
import { Panel, Stat } from '../../../../components/design/Panel';
import {
  Bar,
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
import { completion, filterSetCards, percent, type OwnFilter } from '../../../../utils/collectionStats';

const SetStatsPage: React.FC = () => {
  const router = useRouter();
  const { currency } = useTheme();
  const code = String(router.query.code ?? '');
  const [filter, setFilter] = useState<OwnFilter>('all');
  const [rarity, setRarity] = useState('');

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['setStats', code, currency],
    queryFn: () => fetchSetStats(code, currency),
    enabled: code !== '',
  });

  const cards = useMemo(() => filterSetCards(stats?.cards ?? [], filter, rarity), [stats?.cards, filter, rarity]);
  const price = (v: number | null | undefined): string => formatPrice(v, currency);
  const t = stats?.totals;

  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      <StatsHeader
        loading={isLoading}
        crumbs={
          <>
            <Link href="/collection" style={link}>Collection</Link> /{' '}
            <Link href="/collection/stats" style={link}>Stats</Link> / set
          </>
        }
        title={
          stats != null ? (
            <>
              {stats.setName} <span className="dim" style={{ fontSize: 16 }}>{stats.setCode.toUpperCase()}</span>
            </>
          ) : (
            'Set statistics'
          )
        }
      />

      {error != null && (
        <div className="mono" style={{ padding: 20, color: 'var(--neg)' }}>
          Could not load set statistics: {error instanceof Error ? error.message : String(error)}
        </div>
      )}
      {!isLoading && stats === null && (
        <div className="mono" style={{ padding: 20 }}>No printings with set code {code.toUpperCase()}.</div>
      )}

      {stats != null && t != null && (
        <>
          <StatRow>
            <Stat
              label="COMPLETION"
              value={`${t.ownedPrintings} / ${t.printings}`}
              sub={`${percent(completion(t.ownedPrintings, t.printings))} of the printings`}
              accent
            />
            <Stat label="COPIES" value={t.copies} sub={`${t.foilCopies} foil`} />
            <Stat label="VALUE OWNED" value={price(t.value)} sub={priceSourceLabel(currency)} />
            <Stat
              label="TO COMPLETE"
              value={price(t.costToComplete)}
              sub={t.unpricedMissing > 0 ? `one of each missing, ${t.unpricedMissing} unpriced` : 'one of each missing'}
            />
          </StatRow>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(280px, 1fr) minmax(0, 3fr)',
              gap: 16,
              padding: 20,
              alignItems: 'start',
            }}
          >
            <Panel title="By rarity">
              <table className="mono tnum" style={statTable}>
                <thead>
                  <tr className="dim" style={headRow}>
                    <th style={cell}>Rarity</th>
                    <th style={num}>Owned</th>
                    <th style={cell} />
                    <th style={num}>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.rarities.map(r => (
                    <tr key={r.rarity} style={bodyRow}>
                      <td style={cell} className="uc">
                        <button
                          type="button"
                          onClick={() => setRarity(rarity === r.rarity ? '' : r.rarity)}
                          aria-pressed={rarity === r.rarity}
                          style={{
                            fontSize: 11,
                            padding: 0,
                            background: 'none',
                            border: 'none',
                            color: rarity === r.rarity ? 'var(--accent)' : 'var(--ink)',
                            cursor: 'pointer',
                          }}
                          className="uc"
                        >
                          {r.rarity || 'other'}
                        </button>
                      </td>
                      <td style={num}>
                        {r.owned}/{r.printings}
                      </td>
                      <td style={{ ...cell, width: '35%' }}>
                        <Bar share={completion(r.owned, r.printings)} />
                      </td>
                      <td style={num}>{price(r.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="mono dim" style={{ fontSize: 10, marginTop: 6 }}>
                Click a rarity to filter the list.
              </div>
            </Panel>

            <Panel
              title={`Printings (${cards.length})${rarity !== '' ? ` · ${rarity}` : ''}`}
              right={
                <FilterButtons
                  value={filter}
                  onChange={setFilter}
                  options={[
                    { id: 'all', label: 'all' },
                    { id: 'owned', label: 'owned' },
                    { id: 'missing', label: 'missing' },
                  ]}
                />
              }
            >
              <table className="mono tnum" style={statTable}>
                <thead>
                  <tr className="dim" style={headRow}>
                    <th style={num}>#</th>
                    <th style={cell}>Card</th>
                    <th style={cell}>Rarity</th>
                    <th style={num}>Owned</th>
                    <th style={num}>Foil</th>
                    <th style={num}>Price</th>
                    <th style={num}>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {cards.map(c => (
                    <tr key={c.cardId} style={{ ...bodyRow, opacity: c.owned ? 1 : 0.6 }}>
                      <td style={num} className="dim">
                        {c.collectorNumber}
                      </td>
                      <td style={{ ...cell, whiteSpace: 'normal' }}>
                        <Link href={`/cards/${slugify(c.title)}?printing=${c.cardId}`} style={link}>
                          {c.title}
                        </Link>
                      </td>
                      <td style={cell} className="uc dim">
                        {c.rarity}
                      </td>
                      <td style={num}>{c.regular || ''}</td>
                      <td style={num}>{c.foil > 0 ? `${c.foil} · ${price(c.foilPrice)}` : ''}</td>
                      <td style={num}>{price(c.unitPrice)}</td>
                      <td style={num}>{c.owned ? price(c.value) : ''}</td>
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

export default SetStatsPage;
