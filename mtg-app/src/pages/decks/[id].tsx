/**
 * Deck editor + analysis page — Phases 4 and 5.
 *
 * All card/deck data is fetched at runtime via JSON:API.
 * The page has two tabs: Editor and Analysis.
 *
 * Route: /decks/:id  (Gatsby client-only route via [id].tsx)
 */

import React, { useState, useMemo } from 'react';
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
    mutationFn: ({
      cardId,
      qty,
      isSideboard,
    }: {
      cardId: string;
      qty: number;
      isSideboard: boolean;
    }) => setCardQuantityInDeck(cardId, qty, isSideboard, cards),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['deckCards', deckId] }),
  });

  const remove = useMutation({
    mutationFn: ({ cardId, isSideboard }: { cardId: string; isSideboard: boolean }) =>
      removeCardFromDeck(cardId, isSideboard, cards),
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
            onClick={() =>
              updateQty.mutate({ cardId: dc.card.id, qty: dc.quantity - 1, isSideboard: dc.isSideboard })
            }
            disabled={dc.quantity <= 1}
            style={{ width: 24 }}
          >
            -
          </button>
          <span style={{ margin: '0 0.5rem' }}>{dc.quantity}</span>
          <button
            type="button"
            onClick={() =>
              updateQty.mutate({ cardId: dc.card.id, qty: dc.quantity + 1, isSideboard: dc.isSideboard })
            }
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
              void remove.mutateAsync({ cardId: dc.card.id, isSideboard: dc.isSideboard }).then(() =>
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
            onClick={() => remove.mutate({ cardId: dc.card.id, isSideboard: dc.isSideboard })}
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
      <p
        style={{
          fontWeight: 'bold',
          color: mainCount === 60 ? 'green' : mainCount > 60 ? 'red' : '#555',
        }}
      >
        Main deck: {mainCount} / 60
        {sbCount > 0 && `  |  Sideboard: ${sbCount}`}
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
// Suggestions tab
// ---------------------------------------------------------------------------

const DeckSuggestions: React.FC<{ deckNid: number }> = ({ deckNid }) => {
  const [limit, setLimit] = useState(10);

  const { data: suggestions = [], isFetching, isError, refetch } = useQuery<CardSuggestion[]>({
    queryKey: ['deckSuggestions', deckNid, limit],
    queryFn: () => fetchCardSuggestions(deckNid, limit),
    enabled: false,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div>
      <p style={{ margin: '0 0 1rem', color: '#555' }}>
        AI-powered card suggestions based on the deck's semantic profile.
        Results come from Milvus vector search and are ranked by Ollama.
      </p>

      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '1.25rem' }}>
        <label htmlFor="sugg-limit" style={{ fontSize: '0.9rem' }}>
          Suggestions:
        </label>
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
            padding: '0.35rem 1rem',
            cursor: isFetching ? 'default' : 'pointer',
            background: '#333',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
            fontSize: '0.9rem',
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
            {suggestions.map((s, i) => (
              <tr key={s.card.nid} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '0.5rem 0.5rem', color: '#888', width: 30 }}>{i + 1}</td>
                <td style={{ padding: '0.5rem 0.5rem', fontWeight: 500 }}>{s.card.name}</td>
                <td style={{ padding: '0.5rem 0.5rem', color: '#444' }}>{s.reason}</td>
                <td style={{ padding: '0.5rem 0.5rem', textAlign: 'right', color: '#666' }}>
                  {(s.score * 100).toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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

  const coaching = useQuery({
    queryKey: ['deckCoach', deckTitle, format, cards.length],
    queryFn: () => fetchDeckCoaching({ format, deckTitle, metrics: buildMetrics() }),
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
  const [tab, setTab] = useState<'editor' | 'analysis' | 'suggestions'>('editor');

  const { data: deck, isLoading: deckLoading } = useQuery({
    queryKey: ['deck', slug],
    queryFn: () => fetchDeckBySlug(slug),
    enabled: slug != null,
  });

  const deckId = deck?.id;

  const { data: deckCards = [], isLoading: cardsLoading } = useQuery<DeckCardWithCard[]>({
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
      </div>

      {cardsLoading && tab !== 'suggestions' ? (
        <p>Loading cards...</p>
      ) : tab === 'editor' ? (
        <DeckEditor deckId={deckId!} cards={deckCards} />
      ) : tab === 'analysis' ? (
        <DeckAnalysis cards={deckCards} format={deck.attributes.field_format} deckTitle={deck.attributes.title} />
      ) : (
        <DeckSuggestions deckNid={deck.attributes.nid} />
      )}
    </main>
  );
};

export default DeckPage;
