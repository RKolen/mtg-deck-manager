/**
 * Deck editor + analysis page — Phases 4 and 5.
 *
 * All card/deck data is fetched at runtime via GraphQL.
 * The page has two tabs: Editor and Analysis.
 *
 * Route: /decks/:id  (Gatsby client-only route via [id].tsx)
 */

import React, { useState, useMemo, useRef } from 'react';
import { Link } from 'gatsby';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  CartesianGrid,
} from 'recharts';

import {
  fetchDeckBySlug,
  fetchDeckCardsWithCards,
  findCardsByName,
  addCardToDeck,
  setCardQuantityInDeck,
  removeCardFromDeck,
  updateDeck,
} from '../../services/drupalApi';
import { fetchCardSuggestions, type CardSuggestion } from '../../services/deckSuggestions';
import { fetchDeckCoaching, type DeckCoachMetrics } from '../../services/deckCoach';
import {
  runSimulation,
  fetchSimulationHistory,
  type SimulationResult,
  type SimulationHistoryEntry,
  type TopKiller,
  type GameLog,
} from '../../services/simulationApi';
import {
  fetchMetaDecks,
  fetchMatchupAdvice,
  classifyPlays,
  type MetaDeck,
  type MatchupAdvice,
  type ArchetypeProbability,
} from '../../services/metaApi';
import type { DeckCardWithCard } from '../../types/drupal';
import { slugify } from '../../utils/slugify';
import {
  ALL_COLORS,
  COLOR_LABEL,
  mainDeck,
  sideboard,
  totalCount,
  cardTypeDistribution,
  cmcHistogram,
  averageCmc,
  manaColorDistribution,
  manaRequirement,
  effectiveManaSources,
  totalManaSources,
  manaHandProbability,
  manaColoredCardRatio,
  maxCopiesAllowed,
  isLand,
  type MtgColor,
  classifyType,
} from '../../utils/deckAnalysis';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DeckPageProps {
  params: { id: string };
}

// ---------------------------------------------------------------------------
// Color constants
// ---------------------------------------------------------------------------

const RECHARTS_COLORS: Record<MtgColor, string> = {
  W: '#f0e6c8',
  U: '#4a90d9',
  B: '#555',
  R: '#d9534f',
  G: '#5cb85c',
};

const TYPE_COLORS: Record<string, string> = {
  Land: '#a0c080',
  Creature: '#4a90d9',
  Artifact: '#aaaaaa',
  Enchantment: '#88cc88',
  Planeswalker: '#cc8844',
  Instant: '#5599cc',
  Sorcery: '#cc5555',
  Other: '#999',
};

const PCT_FMT = (v: number): string => `${v.toFixed(1)}%`;

// ---------------------------------------------------------------------------
// Editor tab
// ---------------------------------------------------------------------------

interface EditorProps {
  deckId: string;
  cards: DeckCardWithCard[];
}

const DeckEditor: React.FC<EditorProps> = ({ deckId, cards }) => {
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState<
    { id: string; title: string }[]
  >([]);
  const [searching, setSearching] = useState(false);
  const qc = useQueryClient();

  const updateQty = useMutation({
    mutationFn: ({ slotId, qty }: { slotId: string; qty: number }) =>
      setCardQuantityInDeck(slotId, qty, deckId, cards),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['deckCards', deckId] }),
  });

  const remove = useMutation({
    mutationFn: ({ slotId }: { slotId: string }) =>
      removeCardFromDeck(slotId, deckId, cards),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['deckCards', deckId] }),
  });

  const addCard = useMutation({
    mutationFn: ({
      cardId,
      cardName,
      isSideboard,
    }: {
      cardId: string;
      cardName: string;
      isSideboard: boolean;
    }) => addCardToDeck(deckId, cardId, isSideboard, cards, cardName),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['deckCards', deckId] });
      setSearchResults([]);
      setSearch('');
    },
  });

  async function handleSearch(): Promise<void> {
    if (search.trim() === '') return;
    setSearching(true);
    try {
      const results = await findCardsByName(search.trim());
      setSearchResults(
        results.map(r => ({ id: r.id, title: r.attributes.title })),
      );
    } finally {
      setSearching(false);
    }
  }

  const main = mainDeck(cards);
  const sb = sideboard(cards);
  const mainCount = totalCount(main);
  const sbCount = totalCount(sb);

  // Group main deck cards into sections.
  const GROUPS: { label: string; types: string[] }[] = [
    { label: 'Creatures',  types: ['Creature'] },
    { label: 'Spells',     types: ['Instant', 'Sorcery', 'Enchantment', 'Planeswalker', 'Artifact', 'Other'] },
    { label: 'Lands',      types: ['Land'] },
  ];

  function groupCards(cards: DeckCardWithCard[], types: string[]): DeckCardWithCard[] {
    return cards.filter(dc => types.includes(classifyType(dc.card.field_type_line ?? '')));
  }

  function renderRow(dc: DeckCardWithCard): React.ReactNode {
    const oracleText =
      typeof dc.card.field_oracle_text === 'string'
        ? dc.card.field_oracle_text
        : (dc.card.field_oracle_text as { value?: string } | null)?.value ?? '';
    const maxCopies = maxCopiesAllowed(
      dc.card.field_type_line ?? '',
      oracleText,
    );
    const atMax = dc.quantity >= maxCopies;
    return (
      <tr key={dc.card.id + String(dc.isSideboard)}>
        <td style={{ padding: '0.25rem 0.5rem' }}>
          <Link
            to={`/cards/${slugify(dc.card.title)}`}
            style={{ color: 'inherit', textDecoration: 'none', fontWeight: 'bold' }}
          >
            {dc.card.title}
          </Link>
          <span style={{ marginLeft: 8, color: '#999', fontSize: '0.8rem' }}>
            {dc.card.field_mana_cost}
          </span>
        </td>
        <td style={{ padding: '0.25rem 0.5rem', textAlign: 'center' }}>
          <button
            type="button"
            onClick={() => updateQty.mutate({ slotId: dc.id, qty: dc.quantity - 1 })}
            disabled={dc.quantity <= 1}
            style={{ width: 24 }}
          >
            -
          </button>
          <span style={{ margin: '0 0.5rem' }}>{dc.quantity}</span>
          <button
            type="button"
            onClick={() => updateQty.mutate({ slotId: dc.id, qty: dc.quantity + 1 })}
            disabled={atMax}
            title={atMax ? `Max ${maxCopies === Infinity ? 'unlimited' : maxCopies} copies` : undefined}
            style={{ width: 24 }}
          >
            +
          </button>
        </td>
        <td style={{ padding: '0.25rem 0.5rem', textAlign: 'center' }}>
          <button
            type="button"
            onClick={() => {
              void remove.mutateAsync({ slotId: dc.id }).then(() =>
                addCard.mutate({ cardId: dc.card.id, cardName: dc.card.title, isSideboard: !dc.isSideboard }),
              );
            }}
            style={{ fontSize: '0.75rem' }}
            title={dc.isSideboard ? 'Move to main' : 'Move to sideboard'}
          >
            {dc.isSideboard ? 'To main' : 'To SB'}
          </button>
        </td>
        <td style={{ padding: '0.25rem 0.5rem', textAlign: 'center' }}>
          <button
            type="button"
            onClick={() => remove.mutate({ slotId: dc.id })}
            aria-label="Remove card"
          >
            x
          </button>
        </td>
      </tr>
    );
  }

  return (
    <div>
      {/* Card count banner */}
      <p style={{ fontWeight: 'bold', margin: '0 0 0.75rem' }}>
        <span style={{ color: mainCount >= 60 ? (mainCount > 60 ? 'red' : 'green') : '#555' }}>
          Main: {mainCount} / 60
        </span>
        {'  |  '}
        <span style={{ color: sbCount > 15 ? 'red' : sbCount > 0 ? 'green' : '#aaa' }}>
          Sideboard: {sbCount} / 15
        </span>
      </p>

      {/* Search */}
      <div style={{ display: 'flex', gap: 8, marginBottom: '1rem' }}>
        <input
          type="search"
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') void handleSearch();
          }}
          placeholder="Search card name..."
          style={{ flex: 1 }}
        />
        <button type="button" onClick={() => void handleSearch()} disabled={searching}>
          {searching ? 'Searching...' : 'Search'}
        </button>
      </div>

      {searchResults.length > 0 && (
        <ul
          style={{
            listStyle: 'none',
            padding: 0,
            border: '1px solid #ccc',
            borderRadius: 4,
            marginBottom: '1rem',
            maxHeight: 220,
            overflowY: 'auto',
          }}
        >
          {searchResults.map(r => (
            <li
              key={r.id}
              style={{
                display: 'flex',
                gap: 8,
                padding: '0.4rem 0.75rem',
                borderBottom: '1px solid #eee',
              }}
            >
              <span style={{ flex: 1 }}>{r.title}</span>
              <button
                type="button"
                onClick={() => addCard.mutate({ cardId: r.id, cardName: r.title, isSideboard: false })}
              >
                + Main
              </button>
              <button
                type="button"
                onClick={() => addCard.mutate({ cardId: r.id, cardName: r.title, isSideboard: true })}
              >
                + SB
              </button>
            </li>
          ))}
          <li style={{ padding: '0.25rem 0.75rem' }}>
            <button
              type="button"
              onClick={() => setSearchResults([])}
              style={{ fontSize: '0.8rem' }}
            >
              Clear results
            </button>
          </li>
        </ul>
      )}

      {/* Main deck — grouped by type */}
      {main.length === 0 ? (
        <p style={{ color: '#888' }}>No cards in main deck yet.</p>
      ) : (
        GROUPS.map(group => {
          const grouped = groupCards(main, group.types);
          if (grouped.length === 0) return null;
          const groupCount = totalCount(grouped);
          return (
            <section key={group.label} style={{ marginBottom: '1.25rem' }}>
              <h3 style={{ margin: '0 0 0.4rem', borderBottom: '2px solid #ddd', paddingBottom: '0.25rem' }}>
                {group.label}
                <span style={{ marginLeft: 8, color: '#888', fontWeight: 'normal', fontSize: '0.9rem' }}>
                  ({groupCount})
                </span>
              </h3>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #eee' }}>
                    <th style={{ textAlign: 'left', padding: '0.2rem 0.5rem' }}>Card</th>
                    <th style={{ padding: '0.2rem 0.5rem' }}>Qty</th>
                    <th style={{ padding: '0.2rem 0.5rem' }}>Move</th>
                    <th style={{ padding: '0.2rem 0.5rem' }}>Del</th>
                  </tr>
                </thead>
                <tbody>{grouped.map(dc => renderRow(dc))}</tbody>
              </table>
            </section>
          );
        })
      )}

      {/* Sideboard */}
      <section style={{ marginTop: '1.5rem' }}>
        <h3 style={{ margin: '0 0 0.4rem', borderBottom: '2px solid #ddd', paddingBottom: '0.25rem' }}>
          Sideboard
          <span style={{ marginLeft: 8, color: '#888', fontWeight: 'normal', fontSize: '0.9rem' }}>
            ({sbCount})
          </span>
        </h3>
        {sb.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #eee' }}>
                <th style={{ textAlign: 'left', padding: '0.2rem 0.5rem' }}>Card</th>
                <th style={{ padding: '0.2rem 0.5rem' }}>Qty</th>
                <th style={{ padding: '0.2rem 0.5rem' }}>Move</th>
                <th style={{ padding: '0.2rem 0.5rem' }}>Del</th>
              </tr>
            </thead>
            <tbody>{sb.map(dc => renderRow(dc))}</tbody>
          </table>
        ) : (
          <p style={{ color: '#888' }}>Sideboard is empty.</p>
        )}
      </section>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Analysis tab
// ---------------------------------------------------------------------------

const DeckAnalysis: React.FC<{ cards: DeckCardWithCard[]; format: string; deckTitle: string }> = ({ cards, format, deckTitle }) => {
  const [selectedColor, setSelectedColor] = useState<MtgColor>('W');

  const main = mainDeck(cards);

  const typeDist = useMemo(() => cardTypeDistribution(cards), [cards]);
  const histogram = useMemo(() => cmcHistogram(cards), [cards]);
  const avgCmc = useMemo(() => averageCmc(cards), [cards]);
  const manaDist = useMemo(() => manaColorDistribution(cards), [cards]);
  const manaReq = useMemo(() => manaRequirement(cards), [cards]);
  const sources = useMemo(() => effectiveManaSources(cards), [cards]);
  const totalSources = useMemo(() => totalManaSources(cards), [cards]);
  const handTable = useMemo(
    () => manaHandProbability(cards, selectedColor),
    [cards, selectedColor],
  );
  const ratio = useMemo(() => manaColoredCardRatio(cards), [cards]);
  const mainCount = totalCount(main);

  if (mainCount === 0) {
    return <p>Add cards to the main deck to see analysis.</p>;
  }

  // CMC histogram data.
  const cmcData = Array.from({ length: 8 }, (_, i) => ({
    cmc: i < 7 ? String(i) : '7+',
    count: histogram[i] ?? 0,
  }));

  // Type distribution data.
  const typeData = Object.entries(typeDist).map(([name, value]) => ({
    name,
    value,
  }));

  // Mana color distribution data.
  const manaDistData = ALL_COLORS.filter(
    c => manaDist.colorSourcePct[c] > 0 || manaDist.colorPipPct[c] > 0,
  ).map(c => ({
    color: c,
    name: COLOR_LABEL[c],
    sourcePct: Number(manaDist.colorSourcePct[c].toFixed(1)),
    pipPct: Number(manaDist.colorPipPct[c].toFixed(1)),
  }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Summary stats */}
      <section>
        <h3 style={{ marginTop: 0 }}>Summary</h3>
        <dl
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
            gap: '0.5rem',
          }}
        >
          {[
            ['Cards (main)', mainCount],
            ['Avg CMC', avgCmc.toFixed(2)],
            ['Mana sources', totalSources.toFixed(1)],
            ['Mana/colored ratio', ratio.toFixed(2)],
          ].map(([label, value]) => (
            <div
              key={String(label)}
              style={{
                background: '#f5f5f0',
                padding: '0.5rem 0.75rem',
                borderRadius: 4,
              }}
            >
              <dt style={{ fontSize: '0.8rem', color: '#666' }}>{label}</dt>
              <dd style={{ margin: 0, fontWeight: 'bold', fontSize: '1.25rem' }}>
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      {/* Mana curve */}
      <section>
        <h3>Mana curve (avg CMC {avgCmc.toFixed(2)})</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={cmcData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="cmc" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" fill="#4a90d9" />
          </BarChart>
        </ResponsiveContainer>
      </section>

      {/* Card type distribution */}
      <section>
        <h3>Card types</h3>
        <div style={{ display: 'flex', gap: '2rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <ResponsiveContainer width={220} height={220}>
            <PieChart>
              <Pie
                data={typeData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={80}
              >
                {typeData.map(entry => (
                  <Cell
                    key={entry.name}
                    fill={TYPE_COLORS[entry.name] ?? '#ccc'}
                  />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {typeData.map(d => (
              <li key={d.name} style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                <span
                  style={{
                    width: 14,
                    height: 14,
                    background: TYPE_COLORS[d.name] ?? '#ccc',
                    display: 'inline-block',
                    borderRadius: 2,
                    marginTop: 2,
                  }}
                />
                {d.name}: {d.value}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Mana color distribution */}
      {manaDistData.length > 0 && (
        <section>
          <h3>Mana color distribution</h3>
          <p style={{ fontSize: '0.85rem', color: '#555', margin: '0 0 0.5rem' }}>
            Source % = share of mana sources producing each colour.
            Pip % = share of coloured pips demanded by spells.
            Bars close together mean a well-fitted manabase.
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={manaDistData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis tickFormatter={PCT_FMT} domain={[0, 100]} />
              <Tooltip formatter={(v: number) => PCT_FMT(v)} />
              <Legend />
              <Bar dataKey="sourcePct" name="Source %" fill="#82ca9d" />
              <Bar dataKey="pipPct" name="Pip demand %" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>

          <table
            style={{
              marginTop: '0.5rem',
              borderCollapse: 'collapse',
              fontSize: '0.85rem',
            }}
          >
            <thead>
              <tr>
                <th style={{ padding: '0.25rem 0.75rem', textAlign: 'left' }}>Color</th>
                <th style={{ padding: '0.25rem 0.75rem' }}>Sources</th>
                <th style={{ padding: '0.25rem 0.75rem' }}>Pip demand</th>
                <th style={{ padding: '0.25rem 0.75rem' }}>Source %</th>
                <th style={{ padding: '0.25rem 0.75rem' }}>Pip %</th>
              </tr>
            </thead>
            <tbody>
              {ALL_COLORS.filter(
                c => sources[c] > 0 || manaReq[c] > 0,
              ).map(c => (
                <tr key={c} style={{ borderTop: '1px solid #eee' }}>
                  <td style={{ padding: '0.25rem 0.75rem' }}>
                    <span
                      style={{
                        display: 'inline-block',
                        width: 12,
                        height: 12,
                        background: RECHARTS_COLORS[c],
                        marginRight: 6,
                        border: '1px solid #999',
                        borderRadius: 2,
                      }}
                    />
                    {COLOR_LABEL[c]}
                  </td>
                  <td style={{ padding: '0.25rem 0.75rem', textAlign: 'center' }}>
                    {sources[c].toFixed(1)}
                  </td>
                  <td style={{ padding: '0.25rem 0.75rem', textAlign: 'center' }}>
                    {manaReq[c].toFixed(1)}
                  </td>
                  <td style={{ padding: '0.25rem 0.75rem', textAlign: 'center' }}>
                    {PCT_FMT(manaDist.colorSourcePct[c])}
                  </td>
                  <td style={{ padding: '0.25rem 0.75rem', textAlign: 'center' }}>
                    {PCT_FMT(manaDist.colorPipPct[c])}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Mana hand probability */}
      <section>
        <h3>Mana hand probability</h3>
        <p style={{ fontSize: '0.85rem', color: '#555', margin: '0 0 0.5rem' }}>
          P(drawing at least k sources of colour C by turn T) from a 7-card
          opening hand. Assumes no mulligans.
        </p>
        <label htmlFor="color-select" style={{ marginRight: 8 }}>
          Colour:
        </label>
        <select
          id="color-select"
          value={selectedColor}
          onChange={e => setSelectedColor(e.target.value as MtgColor)}
          style={{ marginBottom: '0.75rem' }}
        >
          {ALL_COLORS.map(c => (
            <option key={c} value={c}>
              {COLOR_LABEL[c]} ({sources[c].toFixed(1)} sources)
            </option>
          ))}
        </select>

        <table
          style={{
            borderCollapse: 'collapse',
            fontSize: '0.85rem',
            width: '100%',
          }}
        >
          <thead>
            <tr style={{ background: '#f5f5f0' }}>
              <th style={{ padding: '0.4rem 0.75rem', textAlign: 'left' }}>
                Turn
              </th>
              {handTable.sourcesNeeded.map(k => (
                <th key={k} style={{ padding: '0.4rem 0.75rem' }}>
                  {'\u2265'}{k} source
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {handTable.turns.map((turn, ti) => (
              <tr key={turn} style={{ borderTop: '1px solid #eee' }}>
                <td style={{ padding: '0.3rem 0.75rem' }}>Turn {turn}</td>
                {handTable.table[ti]!.map((prob, ki) => (
                  <td
                    key={ki}
                    style={{
                      padding: '0.3rem 0.75rem',
                      textAlign: 'center',
                      background: `rgba(74,144,217,${prob * 0.4})`,
                    }}
                  >
                    {(prob * 100).toFixed(1)}%
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <CoachPanel cards={cards} format={format} deckTitle={deckTitle} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Simulate tab (Phase 10B)
// ---------------------------------------------------------------------------

interface DeckSimulateProps {
  deckNid: number;
  format: string;
  deckTitle: string;
}

const GAME_COUNT_OPTIONS = [50, 200] as const;

/** Single expandable game log panel */
const GameLogPanel: React.FC<{ log: GameLog; index: number }> = ({ log, index }) => {
  const [open, setOpen] = useState(false);
  const label = `Game ${index + 1}: ${log.onThePlay ? 'on the play' : 'on the draw'} — ${log.winner === 0 ? '✓ WIN' : '✗ LOSS'} on turn ${log.finalTurn}`;
  const labelColor = log.winner === 0 ? '#27ae60' : '#c0392b';

  return (
    <div style={{ border: '1px solid #ddd', borderRadius: 4, marginBottom: 6 }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', textAlign: 'left', background: '#f9f9f6',
          padding: '0.5rem 0.75rem', border: 'none', cursor: 'pointer',
          fontSize: '0.88rem', fontWeight: 500, color: labelColor,
          display: 'flex', justifyContent: 'space-between',
        }}
      >
        <span>{label}</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div style={{ padding: '0.75rem', fontSize: '0.85rem' }}>
          {/* Opening hand */}
          <div style={{ marginBottom: '0.75rem' }}>
            <strong>Opening hand</strong>
            {log.playerMulligan > 0 && (
              <span style={{ color: '#888', marginLeft: 8 }}>({log.playerMulligan} mulligan{log.playerMulligan > 1 ? 's' : ''})</span>
            )}
            <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {log.playerOpeningHand.map((card, i) => (
                <span key={i} style={{
                  background: '#e8f0fe', padding: '2px 6px', borderRadius: 3, fontSize: '0.8rem',
                }}>
                  {card}
                </span>
              ))}
            </div>
          </div>

          {/* Turn-by-turn log */}
          <div>
            <strong>Turn log</strong>
            <div style={{ marginTop: 6, display: 'grid', gridTemplateColumns: '80px 1fr', gap: '2px 12px', alignItems: 'start' }}>
              {log.turns.map((ev, i) => {
                const isPlayer = ev.player === 0;
                const lifeStr = `${ev.lifeTotals[0]}↔${ev.lifeTotals[1]}`;
                return (
                  <React.Fragment key={i}>
                    <div style={{ color: isPlayer ? '#2c5f8a' : '#8a2c2c', fontWeight: 500, paddingTop: 2, whiteSpace: 'nowrap' }}>
                      T{ev.turn} {isPlayer ? 'You' : 'Opp'}
                    </div>
                    <div style={{ paddingTop: 2 }}>
                      {ev.plays.length === 0 ? (
                        <span style={{ color: '#aaa' }}>pass</span>
                      ) : (
                        ev.plays.map((p, j) => (
                          <span key={j} style={{ marginRight: 8, color: '#333' }}>{p}</span>
                        ))
                      )}
                      {ev.damageDealt > 0 && (
                        <span style={{ color: '#b03030', marginLeft: 4 }}>
                          ⚔ {ev.damageDealt} dmg
                        </span>
                      )}
                      <span style={{ color: '#999', marginLeft: 8, fontSize: '0.78rem' }}>
                        ♥ {lifeStr} | hand {ev.handSize} | board {ev.creaturesInPlay} ({ev.boardPower}⚔)
                      </span>
                    </div>
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* Final state */}
          <div style={{ marginTop: 8, color: '#555', fontSize: '0.82rem' }}>
            Final life: You {log.playerFinalLife} / Opp {log.opponentFinalLife}
            {log.winCondition && <span style={{ marginLeft: 8 }}>({log.winCondition})</span>}
          </div>
        </div>
      )}
    </div>
  );
};

const PCT_COLOR = (pct: number) =>
  pct >= 55 ? '#27ae60' : pct >= 45 ? '#e67e22' : '#e74c3c';

const DeckSimulate: React.FC<DeckSimulateProps> = ({ deckNid, format, deckTitle }) => {
  const queryClient = useQueryClient();
  const [selectedArchetype, setSelectedArchetype] = useState('');
  const [games, setGames] = useState<50 | 200>(50);
  const [useLlm, setUseLlm] = useState(false);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: metaDecks = [] } = useQuery({
    queryKey: ['metaDecks', format],
    queryFn: () => import('../../services/metaApi').then(m => m.fetchMetaDecks(format)),
    staleTime: 10 * 60 * 1000,
  });

  const historyKey = ['simHistory', deckNid];
  const { data: history = [] } = useQuery<SimulationHistoryEntry[]>({
    queryKey: historyKey,
    queryFn: () => fetchSimulationHistory(deckNid, 20),
    staleTime: 0,
  });

  async function handleRun(archetype = selectedArchetype): Promise<void> {
    if (!archetype) return;
    setSelectedArchetype(archetype);
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await runSimulation({ playerDeckId: deckNid, opponentArchetype: archetype, format, games, useLlm });
      setResult(r);
      void queryClient.invalidateQueries({ queryKey: historyKey });
    } catch (e: unknown) {
      const axiosErr = e as { response?: { status: number; data?: unknown }; message?: string };
      const status = axiosErr?.response?.status;
      const detail = axiosErr?.response?.data
        ? JSON.stringify(axiosErr.response.data).slice(0, 200)
        : axiosErr?.message ?? 'unknown error';
      setError(`Simulation failed (${status ?? 'network error'}): ${detail}`);
    } finally {
      setRunning(false);
    }
  }

  const winPct = result ? (result.winRate * 100).toFixed(1) : null;
  const playPct = result ? (result.onThePlay.winRate * 100).toFixed(1) : null;
  const drawPct = result ? (result.onTheDraw.winRate * 100).toFixed(1) : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <p style={{ margin: 0, fontSize: '0.9rem', color: '#555' }}>
          Simulate {deckTitle} against a meta archetype, or play an interactive game.
          Requires <code>mtg-sim/sim/main.py</code> on port 8002.
        </p>
        {selectedArchetype && (
          <a
            href={`/play?deckId=${deckNid}&vs=${encodeURIComponent(selectedArchetype)}&format=${encodeURIComponent(format)}&play=1`}
            target="_blank"
            rel="noreferrer"
            style={{ display: 'inline-block', padding: '0.4rem 1rem', background: '#1a3a1a', color: '#2ecc71', border: '1px solid #2ecc71', borderRadius: 4, fontWeight: 600, fontSize: '0.88rem', textDecoration: 'none' }}
          >
            🃏 Play vs {selectedArchetype}
          </a>
        )}
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>Opponent archetype</span>
          <select value={selectedArchetype} onChange={e => setSelectedArchetype(e.target.value)} style={{ minWidth: 200 }}>
            <option value="">Select archetype…</option>
            {metaDecks.map(d => (
              <option key={d.id} value={d.attributes.title}>{d.attributes.title}</option>
            ))}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>Games</span>
          <select value={games} onChange={e => setGames(Number(e.target.value) as 50 | 200)}>
            {GAME_COUNT_OPTIONS.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}>
          <input type="checkbox" checked={useLlm} onChange={e => setUseLlm(e.target.checked)} />
          LLM key moments
        </label>
        <button
          type="button" onClick={() => void handleRun()}
          disabled={!selectedArchetype || running}
          style={{ padding: '0.4rem 1.25rem', background: '#333', color: '#fff', border: 'none', borderRadius: 4, cursor: selectedArchetype && !running ? 'pointer' : 'default' }}
        >
          {running ? 'Simulating…' : 'Run simulation'}
        </button>
      </div>

      {running && <p style={{ color: '#888', fontStyle: 'italic' }}>Running {games} games against {selectedArchetype}…</p>}
      {error && <p style={{ color: '#c00', fontSize: '0.88rem' }}>{error}</p>}

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

          {/* Win-rate summary */}
          <section style={{ background: '#f8f8f5', border: '1px solid #ddd', borderRadius: 4, padding: '1rem' }}>
            <h3 style={{ margin: '0 0 0.75rem' }}>{result.playerDeck} vs {result.opponentArchetype} — {result.games} games</h3>
            <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
              {[
                ['Overall', winPct, result.wins, result.losses],
                ['On the play', playPct, result.onThePlay.wins, result.onThePlay.games - result.onThePlay.wins],
                ['On the draw', drawPct, result.onTheDraw.wins, result.onTheDraw.games - result.onTheDraw.wins],
              ].map(([label, pct, w, l]) => (
                <div key={String(label)} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '2rem', fontWeight: 'bold', color: Number(pct) >= 50 ? '#27ae60' : '#c0392b' }}>{pct}%</div>
                  <div style={{ fontSize: '0.8rem', color: '#666' }}>{label}</div>
                  <div style={{ fontSize: '0.8rem', color: '#888' }}>{w}W / {l}L</div>
                </div>
              ))}
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{result.avgTurnWin}</div>
                <div style={{ fontSize: '0.8rem', color: '#666' }}>Avg win turn</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{result.avgTurnLoss}</div>
                <div style={{ fontSize: '0.8rem', color: '#666' }}>Avg loss turn</div>
              </div>
            </div>
          </section>

          {/* Aggregate game stats */}
          {result.mulliganStats && (
            <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
              {[
                ['Avg mulligans', result.mulliganStats.avgPlayerMulligan.toFixed(2)],
                ['7-card keep rate', `${result.mulliganStats.keepRate}%`],
                ['Opp avg mulligans', result.mulliganStats.avgOpponentMulligan.toFixed(2)],
                ['Mana efficiency', `${result.manaEfficiency}%`],
              ].map(([label, val]) => (
                <div key={label} style={{ background: '#f5f5f0', borderRadius: 4, padding: '0.6rem 0.8rem' }}>
                  <div style={{ fontSize: '1.25rem', fontWeight: 600 }}>{val}</div>
                  <div style={{ fontSize: '0.78rem', color: '#666' }}>{label}</div>
                </div>
              ))}
            </section>
          )}

          {/* Life progression chart */}
          {result.lifeProgression && result.lifeProgression.length > 0 && (
            <section>
              <h3 style={{ margin: '0 0 0.5rem' }}>Average life totals by turn</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={result.lifeProgression} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="turn" label={{ value: 'Turn', position: 'insideBottom', offset: -2 }} tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 20]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="avgPlayerLife" name="You" fill="#2c7bb6" />
                  <Bar dataKey="avgOppLife" name="Opponent" fill="#d7191c" />
                </BarChart>
              </ResponsiveContainer>
            </section>
          )}

          {/* Turn-by-turn board development */}
          {result.turnBreakdown && result.turnBreakdown.length > 0 && (
            <section>
              <h3 style={{ margin: '0 0 0.5rem' }}>Board development (your side, avg per game)</h3>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ borderCollapse: 'collapse', fontSize: '0.85rem', minWidth: 500 }}>
                  <thead>
                    <tr style={{ background: '#f5f5f0' }}>
                      {['Turn', 'Avg creatures', 'Avg power', 'Avg hand', 'Avg dmg dealt'].map(h => (
                        <th key={h} style={{ padding: '0.3rem 0.6rem', textAlign: h === 'Turn' ? 'left' : 'right' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.turnBreakdown.map(row => (
                      <tr key={row.turn} style={{ borderTop: '1px solid #eee' }}>
                        <td style={{ padding: '0.3rem 0.6rem' }}>{row.turn}</td>
                        <td style={{ padding: '0.3rem 0.6rem', textAlign: 'right' }}>{row.avgCreatures}</td>
                        <td style={{ padding: '0.3rem 0.6rem', textAlign: 'right' }}>{row.avgBoardPower}</td>
                        <td style={{ padding: '0.3rem 0.6rem', textAlign: 'right' }}>{row.avgHandSize}</td>
                        <td style={{ padding: '0.3rem 0.6rem', textAlign: 'right' }}>{row.avgDamageDealt}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Top killers */}
          {result.topKillers.length > 0 && (
            <section>
              <h3 style={{ margin: '0 0 0.5rem' }}>Top opponent threats in losses</h3>
              <table style={{ borderCollapse: 'collapse', fontSize: '0.9rem', width: '100%', maxWidth: 500 }}>
                <thead>
                  <tr style={{ background: '#f5f5f0' }}>
                    <th style={{ padding: '0.3rem 0.5rem', textAlign: 'left' }}>Card</th>
                    <th style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>Games</th>
                    <th style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>Loss contribution</th>
                  </tr>
                </thead>
                <tbody>
                  {result.topKillers.map((k: TopKiller) => (
                    <tr key={k.card} style={{ borderTop: '1px solid #eee' }}>
                      <td style={{ padding: '0.3rem 0.5rem' }}>{k.card}</td>
                      <td style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>{k.appearances}</td>
                      <td style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>{(k.lossContribution * 100).toFixed(0)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {/* Key moments */}
          {result.keyMoments.length > 0 && (
            <section>
              <h3 style={{ margin: '0 0 0.5rem' }}>Key patterns</h3>
              <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem' }}>
                {result.keyMoments.map((m, i) => <li key={i}>{m}</li>)}
              </ul>
            </section>
          )}

          {/* Sample game logs */}
          {result.gameLogs && result.gameLogs.length > 0 && (
            <section>
              <h3 style={{ margin: '0 0 0.5rem' }}>Sample game logs (first {result.gameLogs.length})</h3>
              {result.gameLogs.map((log, i) => (
                <GameLogPanel key={i} log={log} index={i} />
              ))}
            </section>
          )}
        </div>
      )}

      {/* Simulation history */}
      {history.length > 0 && (
        <section>
          <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>Simulation history</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
                <th style={{ padding: '0.3rem 0.5rem' }}>Opponent</th>
                <th style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>Games</th>
                <th style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>Win %</th>
                <th style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>Play</th>
                <th style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>Draw</th>
                <th style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>Date</th>
                <th style={{ padding: '0.3rem 0.5rem' }} />
              </tr>
            </thead>
            <tbody>
              {history.map(h => {
                const parsed = (() => {
                  try { return JSON.parse(h.resultJson) as SimulationResult; }
                  catch { return null; }
                })();
                const wp = (h.winRate * 100).toFixed(1);
                const pp = parsed ? (parsed.onThePlay.winRate * 100).toFixed(1) : '—';
                const dp = parsed ? (parsed.onTheDraw.winRate * 100).toFixed(1) : '—';
                const date = new Date(h.created).toLocaleDateString();
                return (
                  <tr key={h.id} style={{ borderBottom: '1px solid #eee' }}>
                    <td style={{ padding: '0.4rem 0.5rem', fontWeight: 500 }}>{h.opponent}</td>
                    <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right', color: '#666' }}>{h.games}</td>
                    <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right', fontWeight: 700, color: PCT_COLOR(parseFloat(wp)) }}>{wp}%</td>
                    <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right', color: '#555' }}>{pp !== '—' ? `${pp}%` : '—'}</td>
                    <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right', color: '#555' }}>{dp !== '—' ? `${dp}%` : '—'}</td>
                    <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right', color: '#888', fontSize: '0.8rem' }}>{date}</td>
                    <td style={{ padding: '0.4rem 0.5rem' }}>
                      <button
                        type="button"
                        onClick={() => void handleRun(h.opponent)}
                        disabled={running}
                        style={{ padding: '0.2rem 0.6rem', fontSize: '0.78rem', background: '#f0f0f0', border: '1px solid #ccc', borderRadius: 3, cursor: running ? 'default' : 'pointer' }}
                      >
                        Simulate more
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Suggestions tab
// ---------------------------------------------------------------------------

const DeckSuggestions: React.FC<{ deckNid: number }> = ({ deckNid }) => {
  const [limit, setLimit] = useState(10);
  const [modalCard, setModalCard] = useState<{ name: string; imageUri: string } | null>(null);

  const { data: suggestions = [], isFetching, isError, refetch } = useQuery<CardSuggestion[]>({
    queryKey: ['deckSuggestions', deckNid, limit],
    queryFn: () => fetchCardSuggestions(deckNid, limit),
    enabled: false,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div>
      {/* Card image modal */}
      {modalCard && (
        <div
          role="dialog"
          aria-label={modalCard.name}
          onClick={() => setModalCard(null)}
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(0,0,0,0.75)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <div onClick={e => e.stopPropagation()} style={{ position: 'relative' }}>
            <img
              src={modalCard.imageUri}
              alt={modalCard.name}
              style={{ borderRadius: 12, maxHeight: '80vh', boxShadow: '0 8px 32px rgba(0,0,0,0.6)' }}
            />
            <button
              type="button"
              onClick={() => setModalCard(null)}
              style={{
                position: 'absolute', top: -12, right: -12,
                background: '#333', color: '#fff', border: 'none',
                borderRadius: '50%', width: 28, height: 28,
                cursor: 'pointer', fontSize: '1rem', lineHeight: '28px', textAlign: 'center',
              }}
            >×</button>
          </div>
        </div>
      )}

      <p style={{ margin: '0 0 1rem', color: '#555' }}>
        AI-powered card suggestions based on the deck's semantic profile.
        Results come from Milvus vector search and are ranked by Ollama.
      </p>

      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '1.25rem' }}>
        <label htmlFor="sugg-limit" style={{ fontSize: '0.9rem' }}>Suggestions:</label>
        <select
          id="sugg-limit"
          value={limit}
          onChange={e => setLimit(Number(e.target.value))}
          style={{ padding: '0.25rem 0.5rem', fontSize: '0.9rem' }}
        >
          {[5, 10, 20, 30].map(n => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => void refetch()}
          disabled={isFetching}
          style={{
            padding: '0.35rem 1rem', cursor: isFetching ? 'default' : 'pointer',
            background: '#333', color: '#fff', border: 'none', borderRadius: 4, fontSize: '0.9rem',
          }}
        >
          {isFetching ? 'Thinking...' : 'Get Suggestions'}
        </button>
      </div>

      {isError && (
        <p style={{ color: '#c00' }}>
          Could not load suggestions. Make sure the Milvus index has items and Ollama is running.
        </p>
      )}
      {suggestions.length === 0 && !isFetching && !isError && (
        <p style={{ color: '#777', fontStyle: 'italic' }}>Click 'Get Suggestions' to start.</p>
      )}

      {suggestions.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #ccc' }}>
              <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem' }}>#</th>
              <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem' }}>Card</th>
              <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem' }}>Why it fits</th>
              <th style={{ textAlign: 'right', padding: '0.4rem 0.5rem' }}>Score</th>
            </tr>
          </thead>
          <tbody>
            {suggestions.map((s, i) => {
              const hasImage = Boolean(s.card.image_uri);
              return (
                <tr
                  key={s.card.nid}
                  style={{ borderBottom: '1px solid #eee', cursor: hasImage ? 'pointer' : 'default' }}
                  onClick={() => {
                    if (hasImage) setModalCard({ name: s.card.name, imageUri: s.card.image_uri! });
                  }}
                  title={hasImage ? `Click to preview ${s.card.name}` : undefined}
                >
                  <td style={{ padding: '0.5rem 0.5rem', color: '#888', width: 30 }}>{i + 1}</td>
                  <td style={{ padding: '0.5rem 0.5rem', fontWeight: 500 }}>
                    {s.card.name}
                    {hasImage && <span style={{ marginLeft: 6, color: '#aaa', fontSize: '0.78rem' }}>🖼</span>}
                  </td>
                  <td style={{ padding: '0.5rem 0.5rem', color: '#444' }}>{s.reason}</td>
                  <td style={{ padding: '0.5rem 0.5rem', textAlign: 'right', color: '#666' }}>
                    {(s.score * 100).toFixed(1)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Meta Matchup tab (Phase 10A)
// ---------------------------------------------------------------------------

interface DeckMetaMatchupProps {
  deckNid: number;
  format: string;
}

const DeckMetaMatchup: React.FC<DeckMetaMatchupProps> = ({ deckNid, format }) => {
  // --- meta share chart ---
  const { data: metaDecks = [], isLoading: metaLoading } = useQuery<MetaDeck[]>({
    queryKey: ['metaDecks', format],
    queryFn: () => fetchMetaDecks(format),
    staleTime: 10 * 60 * 1000,
  });

  // --- matchup advisor ---
  const [selectedArchetype, setSelectedArchetype] = useState('');
  const [advice, setAdvice] = useState<MatchupAdvice | null>(null);
  const [adviceLoading, setAdviceLoading] = useState(false);
  const [adviceError, setAdviceError] = useState<string | null>(null);

  async function handleGetAdvice(): Promise<void> {
    if (!selectedArchetype) return;
    setAdviceLoading(true);
    setAdviceError(null);
    setAdvice(null);
    const confidence = classifierResults.find(r => r.name === selectedArchetype)?.probability ?? 1.0;
    try {
      const result = await fetchMatchupAdvice({ playerDeckId: deckNid, opponentArchetype: selectedArchetype, confidence, format });
      setAdvice(result);
    } catch {
      setAdviceError('Could not reach the matchup advisor. Make sure Ollama is running.');
    } finally {
      setAdviceLoading(false);
    }
  }

  // --- deck deduction ---
  const inputRef = useRef<HTMLInputElement>(null);
  const [observedInput, setObservedInput] = useState('');
  const [observedPlays, setObservedPlays] = useState<{ card_name: string }[]>([]);
  const [classifierResults, setClassifierResults] = useState<ArchetypeProbability[]>([]);
  const [classifierRunning, setClassifierRunning] = useState(false);

  function addPlay(): void {
    const name = observedInput.trim();
    if (!name) return;
    const next = [...observedPlays, { card_name: name }];
    setObservedPlays(next);
    setObservedInput('');
    inputRef.current?.focus();
    void runClassifier(next);
  }

  async function runClassifier(plays: { card_name: string }[]): Promise<void> {
    if (plays.length === 0) { setClassifierResults([]); return; }
    setClassifierRunning(true);
    const results = await classifyPlays(plays);
    setClassifierResults(results.slice(0, 5));
    setClassifierRunning(false);
  }

  const topArchetypes = metaDecks
    .filter(d => d.attributes.field_meta_share != null)
    .slice(0, 12);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>

      {/* Meta share bar chart */}
      <section>
        <h3 style={{ marginTop: 0 }}>Current {format} meta</h3>
        {metaLoading && <p style={{ color: '#888' }}>Loading meta data…</p>}
        {!metaLoading && topArchetypes.length === 0 && (
          <p style={{ color: '#888', fontStyle: 'italic' }}>
            No meta_deck nodes found for {format}. Run the MTGGoldfish scraper script to populate them.
          </p>
        )}
        {topArchetypes.length > 0 && (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={topArchetypes.map(d => ({
              name: d.attributes.title,
              share: parseFloat(d.attributes.field_meta_share ?? '0'),
            }))} layout="vertical" margin={{ left: 120 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tickFormatter={v => `${v}%`} domain={[0, 'dataMax + 2']} />
              <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v: number) => `${v}%`} />
              <Bar dataKey="share" name="Meta share" fill="#4a90d9" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>

      {/* Deck deduction */}
      <section>
        <h3>Deck deduction</h3>
        <p style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: '#555' }}>
          Enter cards you've seen the opponent play — the classifier updates P(archetype) live.
          {classifierResults.length === 0 && ' (Requires the Python classifier to be running on port 8001.)'}
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: '0.75rem' }}>
          <input
            ref={inputRef}
            type="text"
            value={observedInput}
            onChange={e => setObservedInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') addPlay(); }}
            placeholder="Card name…"
            style={{ flex: 1 }}
          />
          <button type="button" onClick={addPlay}>Add play</button>
          <button type="button" onClick={() => { setObservedPlays([]); setClassifierResults([]); }}>
            Reset
          </button>
        </div>
        {observedPlays.length > 0 && (
          <p style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: '#444' }}>
            Observed: {observedPlays.map(p => p.card_name).join(', ')}
          </p>
        )}
        {classifierRunning && <p style={{ color: '#888', fontStyle: 'italic' }}>Classifying…</p>}
        {classifierResults.length > 0 && (
          <table style={{ borderCollapse: 'collapse', fontSize: '0.85rem', width: '100%', maxWidth: 400 }}>
            <thead>
              <tr style={{ background: '#f5f5f0' }}>
                <th style={{ padding: '0.3rem 0.5rem', textAlign: 'left' }}>Archetype</th>
                <th style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>P(match)</th>
              </tr>
            </thead>
            <tbody>
              {classifierResults.map(r => (
                <tr key={r.name} style={{ borderTop: '1px solid #eee' }}>
                  <td style={{ padding: '0.3rem 0.5rem' }}>
                    <button
                      type="button"
                      onClick={() => setSelectedArchetype(r.name)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline', padding: 0, color: '#333' }}
                    >
                      {r.name}
                    </button>
                  </td>
                  <td style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>
                    {(r.probability * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Matchup advisor */}
      <section>
        <h3>Matchup advice</h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
          <select
            value={selectedArchetype}
            onChange={e => setSelectedArchetype(e.target.value)}
            style={{ flex: 1, minWidth: 160 }}
          >
            <option value="">Select opponent archetype…</option>
            {metaDecks.map(d => (
              <option key={d.id} value={d.attributes.title}>{d.attributes.title}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void handleGetAdvice()}
            disabled={!selectedArchetype || adviceLoading}
            style={{ padding: '0.35rem 1rem', background: '#333', color: '#fff', border: 'none', borderRadius: 4, cursor: selectedArchetype && !adviceLoading ? 'pointer' : 'default' }}
          >
            {adviceLoading ? 'Thinking…' : 'Get advice'}
          </button>
        </div>

        {adviceError && <p style={{ color: '#c00' }}>{adviceError}</p>}

        {advice && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ background: '#f8f8f5', border: '1px solid #ddd', borderRadius: 4, padding: '0.75rem 1rem' }}>
              <strong>Matchup dynamic</strong>
              <p style={{ margin: '0.25rem 0 0' }}>{advice.dynamic}</p>
            </div>

            {advice.threats.length > 0 && (
              <div style={{ background: '#fff5f5', border: '1px solid #fcc', borderRadius: 4, padding: '0.75rem 1rem' }}>
                <strong>Key threats</strong>
                <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem' }}>
                  {advice.threats.map(t => <li key={t}>{t}</li>)}
                </ul>
              </div>
            )}

            {(advice.sideboard.in.length > 0 || advice.sideboard.out.length > 0) && (
              <div style={{ background: '#f5f8ff', border: '1px solid #cce', borderRadius: 4, padding: '0.75rem 1rem' }}>
                <strong>Sideboard</strong>
                <div style={{ display: 'flex', gap: '2rem', marginTop: '0.25rem', flexWrap: 'wrap' }}>
                  {advice.sideboard.in.length > 0 && (
                    <div>
                      <em>IN:</em>
                      <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem' }}>
                        {advice.sideboard.in.map(c => <li key={c}>{c}</li>)}
                      </ul>
                    </div>
                  )}
                  {advice.sideboard.out.length > 0 && (
                    <div>
                      <em>OUT:</em>
                      <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem' }}>
                        {advice.sideboard.out.map(c => <li key={c}>{c}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {advice.keyPlay && (
              <div style={{ background: '#f5fff5', border: '1px solid #cec', borderRadius: 4, padding: '0.75rem 1rem' }}>
                <strong>Key play pattern</strong>
                <p style={{ margin: '0.25rem 0 0' }}>{advice.keyPlay}</p>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Coach panel (Phase 8b)
// ---------------------------------------------------------------------------

interface CoachPanelProps {
  cards: DeckCardWithCard[];
  format: string;
  deckTitle: string;
}

const CoachPanel: React.FC<CoachPanelProps> = ({ cards, format, deckTitle }) => {
  const [open, setOpen] = React.useState(false);

  const buildMetrics = React.useCallback((): DeckCoachMetrics => {
    const main = mainDeck(cards);
    const dist = manaColorDistribution(main);
    const sources = effectiveManaSources(main);
    const histogram = cmcHistogram(main);

    // CMC histogram with string keys for the PHP endpoint.
    const histStr: Record<string, number> = {};
    for (const [k, v] of Object.entries(histogram)) {
      histStr[Number(k) >= 7 ? '7+' : k] = (histStr[Number(k) >= 7 ? '7+' : k] ?? 0) + v;
    }

    // P(≥1 source of colour C) at turns 2 and 3 for each colour with sources.
    const manaHandProb: Record<string, { turn2: number; turn3: number }> = {};
    for (const c of ALL_COLORS) {
      if (sources[c] > 0) {
        const table = manaHandProbability(main, c);
        // turns = [1,2,3,4,5,6,7]; turn2 index = 1, turn3 index = 2; sourcesNeeded[0] = 1
        manaHandProb[c] = {
          turn2: table.table[1]?.[0] ?? 0,
          turn3: table.table[2]?.[0] ?? 0,
        };
      }
    }

    // Non-land mana producers and their card types.
    const nonLandProducers = main.filter(
      dc => dc.card.field_is_mana_producer && !isLand(dc.card.field_type_line ?? ''),
    );
    const producerTypeSet = new Set<string>();
    for (const dc of nonLandProducers) {
      const tl = dc.card.field_type_line ?? '';
      if (/creature/i.test(tl)) producerTypeSet.add('creature');
      if (/artifact/i.test(tl)) producerTypeSet.add('artifact');
      if (/planeswalker/i.test(tl)) producerTypeSet.add('planeswalker');
      if (/enchantment/i.test(tl)) producerTypeSet.add('enchantment');
    }
    const landCount = main.filter(dc => isLand(dc.card.field_type_line ?? '')).reduce(
      (s, dc) => s + dc.quantity, 0,
    );

    return {
      avgCmc: averageCmc(main),
      landCount,
      totalManaSources: totalManaSources(main),
      colorSourcePct: Object.fromEntries(
        ALL_COLORS.map(c => [c, dist.colorSourcePct[c]]),
      ),
      colorPipPct: Object.fromEntries(
        ALL_COLORS.map(c => [c, dist.colorPipPct[c]]),
      ),
      cmcHistogram: histStr,
      manaHandProb,
      manaSources: {
        lands: landCount,
        nonLandProducers: nonLandProducers.reduce((s, dc) => s + dc.quantity, 0),
        producerTypes: [...producerTypeSet],
      },
    };
  }, [cards]);

  const cardSummaries = React.useMemo(() =>
    cards.map(dc => ({
      name: dc.card.title,
      type: dc.card.field_type_line ?? '',
      cmc: dc.card.field_cmc ?? 0,
      oracle: (typeof dc.card.field_oracle_text === 'object'
        ? dc.card.field_oracle_text?.value
        : dc.card.field_oracle_text) ?? '',
    })), [cards]);

  const coaching = useQuery({
    queryKey: ['deckCoach', deckTitle, format, cards.length],
    queryFn: () => fetchDeckCoaching({ format, deckTitle, metrics: buildMetrics(), cards: cardSummaries }),
    enabled: false,
    staleTime: 10 * 60 * 1000,
  });

  return (
    <section style={{ marginTop: '2rem', borderTop: '1px solid #ddd', paddingTop: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: open ? '0.75rem' : 0 }}>
        <h3 style={{ margin: 0 }}>Coach's notes</h3>
        <button
          type="button"
          onClick={() => {
            setOpen(o => !o);
            if (!open && !coaching.data && !coaching.isFetching) void coaching.refetch();
          }}
          style={{ fontSize: '0.85rem', padding: '0.2rem 0.6rem' }}
        >
          {open ? 'Hide' : 'Show'}
        </button>
        {!open && !coaching.data && (
          <button
            type="button"
            onClick={() => { setOpen(true); void coaching.refetch(); }}
            disabled={coaching.isFetching}
            style={{ fontSize: '0.85rem', padding: '0.2rem 0.6rem', background: '#333', color: '#fff', border: 'none', borderRadius: 3, cursor: coaching.isFetching ? 'default' : 'pointer' }}
          >
            {coaching.isFetching ? 'Analysing…' : 'Ask coach'}
          </button>
        )}
      </div>

      {open && (
        <div>
          {coaching.isFetching && (
            <p style={{ color: '#888', fontStyle: 'italic' }}>Ollama is thinking…</p>
          )}
          {coaching.isError && (
            <p style={{ color: '#c00' }}>Could not reach the coach. Make sure Ollama is running.</p>
          )}
          {coaching.data != null && (
            <div
              style={{
                background: '#f8f8f5',
                border: '1px solid #ddd',
                borderRadius: 4,
                padding: '0.75rem 1rem',
                lineHeight: 1.6,
                fontSize: '0.9rem',
                whiteSpace: 'pre-wrap',
              }}
            >
              {coaching.data}
            </div>
          )}
          {coaching.data != null && (
            <button
              type="button"
              onClick={() => void coaching.refetch()}
              disabled={coaching.isFetching}
              style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}
            >
              Re-analyse
            </button>
          )}
        </div>
      )}
    </section>
  );
};

// ---------------------------------------------------------------------------
// Deck header (editable title / format)
// ---------------------------------------------------------------------------

interface DeckHeaderProps {
  deckId: string;
  title: string;
  format: string;
}

const FORMATS = [
  'Standard', 'Modern', 'Legacy', 'Vintage', 'Pioneer', 'Pauper', 'EDH', 'Other',
];

const DeckHeader: React.FC<DeckHeaderProps> = ({ deckId, title, format }) => {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(title);
  const [draftFormat, setDraftFormat] = useState(format);

  const save = useMutation({
    mutationFn: () =>
      updateDeck(deckId, {
        title: draftTitle,
        field_format: draftFormat,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['deck', deckId] });
      setEditing(false);
    },
  });

  if (editing) {
    return (
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          type="text"
          value={draftTitle}
          onChange={e => setDraftTitle(e.target.value)}
          style={{ fontSize: '1.25rem', fontWeight: 'bold' }}
          autoFocus
        />
        <select
          value={draftFormat}
          onChange={e => setDraftFormat(e.target.value)}
        >
          {FORMATS.map(f => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => save.mutate()}
          disabled={save.isPending}
        >
          Save
        </button>
        <button
          type="button"
          onClick={() => {
            setDraftTitle(title);
            setDraftFormat(format);
            setEditing(false);
          }}
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
      <h1 style={{ margin: 0 }}>{title}</h1>
      <span style={{ color: '#666' }}>{format}</span>
      <button type="button" onClick={() => setEditing(true)} style={{ fontSize: '0.8rem' }}>
        Edit
      </button>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

const DeckPage: React.FC<DeckPageProps> = ({ params }) => {
  const { id: slug } = params;
  const [tab, setTab] = useState<'editor' | 'analysis' | 'suggestions' | 'meta' | 'simulate'>('editor');

  const { data: deck, isLoading: deckLoading } = useQuery({
    queryKey: ['deck', slug],
    queryFn: () => fetchDeckBySlug(slug),
    enabled: slug != null,
  });

  const deckId = deck?.id;

  const {
    data: deckCards = [],
    isLoading: cardsLoading,
    isError: cardsError,
    error: cardsErrorDetail,
  } = useQuery<DeckCardWithCard[]>({
    queryKey: ['deckCards', deckId],
    queryFn: () => fetchDeckCardsWithCards(deckId!),
    enabled: deckId != null,
  });

  if (deckLoading) return <main style={{ padding: '1.5rem' }}>Loading deck...</main>;
  if (deck == null) return <main style={{ padding: '1.5rem' }}>Deck not found.</main>;

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: '0.5rem 1.25rem',
    cursor: 'pointer',
    border: 'none',
    borderBottom: active ? '2px solid #333' : '2px solid transparent',
    background: 'none',
    fontWeight: active ? 'bold' : 'normal',
    fontSize: '1rem',
  });

  return (
    <main style={{ padding: '1.5rem', maxWidth: 900 }}>
      <p style={{ margin: '0 0 1rem' }}>
        <Link to="/decks">Back to decks</Link>
      </p>

      <DeckHeader
        deckId={deckId!}
        title={deck.attributes.title}
        format={deck.attributes.field_format}
      />

      {/* Tab bar */}
      <div
        style={{
          display: 'flex',
          borderBottom: '1px solid #ccc',
          margin: '1.25rem 0 1.5rem',
        }}
      >
        <button
          type="button"
          style={tabStyle(tab === 'editor')}
          onClick={() => setTab('editor')}
        >
          Editor
        </button>
        <button
          type="button"
          style={tabStyle(tab === 'analysis')}
          onClick={() => setTab('analysis')}
        >
          Analysis
        </button>
        <button
          type="button"
          style={tabStyle(tab === 'suggestions')}
          onClick={() => setTab('suggestions')}
        >
          Suggestions
        </button>
        <button
          type="button"
          style={tabStyle(tab === 'meta')}
          onClick={() => setTab('meta')}
        >
          Meta
        </button>
        <button
          type="button"
          style={tabStyle(tab === 'simulate')}
          onClick={() => setTab('simulate')}
        >
          Simulate
        </button>
      </div>

      {cardsError ? (
        <p style={{ color: '#c00' }}>
          Failed to load deck cards:{' '}
          {cardsErrorDetail instanceof Error ? cardsErrorDetail.message : 'Unknown error'}
        </p>
      ) : cardsLoading && tab === 'editor' ? (
        <p>Loading cards...</p>
      ) : tab === 'editor' ? (
        <DeckEditor deckId={deckId!} cards={deckCards} />
      ) : tab === 'analysis' ? (
        <DeckAnalysis cards={deckCards} format={deck.attributes.field_format} deckTitle={deck.attributes.title} />
      ) : tab === 'suggestions' ? (
        <DeckSuggestions deckNid={deck.attributes.drupal_internal__nid} />
      ) : tab === 'meta' ? (
        <DeckMetaMatchup deckNid={deck.attributes.drupal_internal__nid} format={deck.attributes.field_format} />
      ) : (
        <DeckSimulate deckNid={deck.attributes.drupal_internal__nid} format={deck.attributes.field_format} deckTitle={deck.attributes.title} />
      )}
    </main>
  );
};

export default DeckPage;
