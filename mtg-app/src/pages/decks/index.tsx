/**
 * Deck library — design system layout wired to Drupal GraphQL.
 * No mock fixtures: decks, cards, colors, and prices come from the API.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchDecks,
  createDeck,
  deleteDeck,
  fetchDeckCardsWithCards,
} from '../../services/drupalApi';
import type { Deck, DeckCardWithCard } from '../../types/drupal';
import { slugify } from '../../utils/slugify';
import { useTheme } from '../../context/ThemeContext';
import { ColorIdStrip, ManaCost } from '../../components/design/Mana';
import { Panel, Stat } from '../../components/design/Panel';
import { HoverPreview } from '../../components/design/HoverPreview';
import {
  formatPriceInt,
  priceSourceLabel,
  totalDeckPrice,
} from '../../utils/prices';

const FORMATS = [
  'Standard',
  'Modern',
  'Legacy',
  'Vintage',
  'Pioneer',
  'Pauper',
  'EDH',
  'Other',
];

function notePreview(notes: string | null): string {
  if (!notes) return '';
  const first = notes.split(/[.\n]/)[0]?.trim() ?? '';
  return first.slice(0, 72);
}

function formatChanged(ts: number | null | undefined): string {
  if (ts == null) return '--';
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) return '--';
  return d.toISOString().slice(5, 10);
}

function deckColorIdentity(cards: DeckCardWithCard[]): string[] {
  const order = ['W', 'U', 'B', 'R', 'G'];
  const set = new Set<string>();
  for (const slot of cards) {
    if (slot.isSideboard) continue;
    for (const c of slot.card.field_color_identity ?? []) {
      if (order.includes(c)) set.add(c);
    }
  }
  return order.filter(c => set.has(c));
}

function mainDeckCount(cards: DeckCardWithCard[]): number {
  return cards
    .filter(c => !c.isSideboard)
    .reduce((s, c) => s + c.quantity, 0);
}

const DecksPage: React.FC = () => {
  const router = useRouter();
  const qc = useQueryClient();
  const { currency, manaSymbolStyle, setCurrency } = useTheme();

  const { data: decks = [], isLoading } = useQuery<Deck[]>({
    queryKey: ['decks'],
    queryFn: fetchDecks,
  });

  const cardQueries = useQueries({
    queries: decks.map(deck => ({
      queryKey: ['deckCards', deck.id],
      queryFn: () => fetchDeckCardsWithCards(deck.id),
      staleTime: 60_000,
      enabled: decks.length > 0,
    })),
  });

  const cardsByDeckId = useMemo(() => {
    const map = new Map<string, DeckCardWithCard[]>();
    decks.forEach((deck, i) => {
      const cards = cardQueries[i]?.data;
      if (cards) map.set(deck.id, cards);
    });
    return map;
  }, [decks, cardQueries]);

  const [sel, setSel] = useState(0);
  const [filter, setFilter] = useState('');
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState('');
  const [format, setFormat] = useState(FORMATS[0] ?? 'Standard');
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [hover, setHover] = useState<{
    name: string;
    imageUri: string | null;
    x: number;
    y: number;
  } | null>(null);

  const filtered = useMemo(
    () =>
      decks.filter(
        d =>
          !filter ||
          d.attributes.title.toLowerCase().includes(filter.toLowerCase()),
      ),
    [decks, filter],
  );

  useEffect(() => {
    if (sel >= filtered.length) setSel(Math.max(0, filtered.length - 1));
  }, [filtered.length, sel]);

  const selected = filtered[sel] ?? null;
  const selectedCards = selected ? cardsByDeckId.get(selected.id) ?? [] : [];

  const createMutation = useMutation({
    mutationFn: () =>
      createDeck({ title, field_format: format, field_notes: null }),
    onSuccess: deck => {
      qc.invalidateQueries({ queryKey: ['decks'] });
      setTitle('');
      setCreating(false);
      void router.push(`/decks/${slugify(deck.attributes.title)}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteDeck(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['decks'] });
      setDeleteConfirm(null);
    },
  });

  const openDeck = (deck: Deck) => {
    void router.push(`/decks/${slugify(deck.attributes.title)}`);
  };

  const totalExpValue = decks.reduce((sum, d) => {
    const cards = cardsByDeckId.get(d.id);
    if (!cards) return sum;
    return sum + totalDeckPrice(cards, currency);
  }, 0);

  const uniqueAcrossDecks = useMemo(() => {
    const names = new Set<string>();
    for (const cards of cardsByDeckId.values()) {
      for (const slot of cards) names.add(slot.card.title);
    }
    return names.size;
  }, [cardsByDeckId]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSel(s => Math.min(filtered.length - 1, s + 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSel(s => Math.max(0, s - 1));
      } else if (e.key === 'Enter' && selected) {
        void router.push(`/decks/${slugify(selected.attributes.title)}`);
      } else if (e.key.toLowerCase() === 'n') {
        setCreating(true);
      } else if (e.key === '/') {
        e.preventDefault();
        document.getElementById('deck-filter')?.focus();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [filtered.length, selected, router]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 420px', gap: 0, height: '100%' }}>
      <div style={{ display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--line)' }}>
        <div
          style={{
            padding: '8px 12px',
            borderBottom: '1px solid var(--line)',
            background: 'var(--bg-1)',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <span className="mono dim" style={{ fontSize: 11 }}>
            FILTER /
          </span>
          <input
            id="deck-filter"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="deck name..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 0,
              outline: 'none',
              fontFamily: 'var(--mono)',
              fontSize: 12,
              color: 'var(--ink)',
            }}
          />
          <span className="mono dim" style={{ fontSize: 10 }}>
            {filtered.length}/{decks.length}
          </span>
          <div className="vr" style={{ height: 14 }} />
          <button
            type="button"
            onClick={() => setCurrency(currency === 'EUR' ? 'USD' : 'EUR')}
            className="mono"
            style={{
              border: '1px solid var(--line-2)',
              padding: '3px 8px',
              borderRadius: 2,
              fontSize: 10,
              color: 'var(--ink-2)',
            }}
            title="Toggle reference currency"
          >
            {currency}
          </button>
          <button
            type="button"
            onClick={() => setCreating(true)}
            style={{
              background: 'var(--accent)',
              color: 'var(--bg)',
              padding: '3px 10px',
              borderRadius: 2,
              fontFamily: 'var(--mono)',
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.08em',
            }}
          >
            + NEW DECK
          </button>
        </div>

        <div style={{ flex: 1, overflow: 'auto' }}>
          {isLoading && (
            <div className="mono dim" style={{ padding: 16 }}>
              Loading decks from Drupal...
            </div>
          )}
          {!isLoading && filtered.length === 0 && (
            <div className="mono dim" style={{ padding: 16 }}>
              No decks yet. Create your first deck.
            </div>
          )}
          <table style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
            <thead
              style={{
                position: 'sticky',
                top: 0,
                background: 'var(--bg-1)',
                zIndex: 1,
              }}
            >
              <tr
                style={{
                  borderBottom: '1px solid var(--line)',
                  color: 'var(--ink-3)',
                  textTransform: 'uppercase',
                  fontSize: 9,
                  letterSpacing: '0.08em',
                }}
              >
                <th style={{ width: 30, textAlign: 'right', paddingRight: 4 }}>#</th>
                <th>Deck</th>
                <th style={{ width: 90 }}>Format</th>
                <th style={{ width: 80 }}>Colors</th>
                <th style={{ width: 60, textAlign: 'right' }}>Cards</th>
                <th style={{ width: 80, textAlign: 'right' }}>Value</th>
                <th style={{ width: 80, textAlign: 'right' }}>Updated</th>
                <th style={{ width: 70 }} />
              </tr>
            </thead>
            <tbody>
              {filtered.map((d, i) => {
                const cards = cardsByDeckId.get(d.id);
                const md = cards ? mainDeckCount(cards) : null;
                const colors = cards ? deckColorIdentity(cards) : [];
                const value = cards ? totalDeckPrice(cards, currency) : null;
                const legal =
                  md != null && (md === 60 || md === 100 || (d.attributes.field_format === 'EDH' && md >= 100));
                return (
                  <tr
                    key={d.id}
                    onMouseEnter={() => setSel(i)}
                    onClick={() => openDeck(d)}
                    style={{
                      borderBottom: '1px solid var(--line)',
                      cursor: 'pointer',
                      background: sel === i ? 'var(--hl)' : 'transparent',
                      borderLeft:
                        sel === i ? '2px solid var(--accent)' : '2px solid transparent',
                    }}
                  >
                    <td style={{ textAlign: 'right', color: 'var(--ink-3)', paddingRight: 4 }}>
                      {String(i + 1).padStart(2, '0')}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--ink)' }}>
                        {d.attributes.title}
                      </div>
                      <div style={{ color: 'var(--ink-3)', fontSize: 10 }}>
                        {notePreview(d.attributes.field_notes)}
                      </div>
                    </td>
                    <td className="dim">{d.attributes.field_format}</td>
                    <td>
                      {cards ? (
                        <ColorIdStrip colors={colors} manaSymbolStyle={manaSymbolStyle} />
                      ) : (
                        <span className="dim">...</span>
                      )}
                    </td>
                    <td
                      className="tnum"
                      style={{
                        textAlign: 'right',
                        color: legal ? 'var(--pos)' : 'var(--ink)',
                      }}
                    >
                      {md ?? '--'}
                    </td>
                    <td className="tnum" style={{ textAlign: 'right' }}>
                      {formatPriceInt(value, currency)}
                    </td>
                    <td className="tnum dim" style={{ textAlign: 'right', fontSize: 10 }}>
                      {formatChanged(d.attributes.changed)}
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      {deleteConfirm === d.id ? (
                        <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                          <button
                            type="button"
                            onClick={() => deleteMutation.mutate(d.id)}
                            style={{ color: 'var(--neg)', fontSize: 10 }}
                          >
                            YES
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteConfirm(null)}
                            style={{ color: 'var(--ink-3)', fontSize: 10 }}
                          >
                            NO
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setDeleteConfirm(d.id)}
                          style={{ color: 'var(--ink-3)', fontSize: 10 }}
                          aria-label={`Delete ${d.attributes.title}`}
                        >
                          DEL
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            padding: 12,
            gap: 16,
            borderBottom: '1px solid var(--line)',
          }}
        >
          <Stat label="DECKS" value={decks.length} sub="in Drupal" />
          <Stat
            label="EXP. VAL"
            value={formatPriceInt(totalExpValue, currency)}
            sub={priceSourceLabel(currency)}
            accent
          />
          <Stat label="UNIQUE" value={uniqueAcrossDecks || '--'} sub="across decks" />
        </div>

        {selected && (
          <DeckPreview
            deck={selected}
            cards={selectedCards}
            manaSymbolStyle={manaSymbolStyle}
            currency={currency}
            onHover={(name, imageUri, e) =>
              setHover({ name, imageUri, x: e.clientX, y: e.clientY })
            }
            onClearHover={() => setHover(null)}
          />
        )}

        {creating && (
          <Panel title="NEW DECK" style={{ border: 0, borderTop: '1px solid var(--line)' }}>
            <form
              onSubmit={e => {
                e.preventDefault();
                if (title.trim() !== '') createMutation.mutate();
              }}
              style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
            >
              <label className="mono" style={{ fontSize: 11 }}>
                Title
                <input
                  type="text"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  required
                  autoFocus
                  style={{
                    display: 'block',
                    width: '100%',
                    marginTop: 4,
                    background: 'var(--bg-2)',
                    border: '1px solid var(--line)',
                    padding: '6px 8px',
                    color: 'var(--ink)',
                  }}
                />
              </label>
              <label className="mono" style={{ fontSize: 11 }}>
                Format
                <select
                  value={format}
                  onChange={e => setFormat(e.target.value)}
                  style={{
                    display: 'block',
                    width: '100%',
                    marginTop: 4,
                    background: 'var(--bg-2)',
                    border: '1px solid var(--line)',
                    padding: '6px 8px',
                    color: 'var(--ink)',
                  }}
                >
                  {FORMATS.map(f => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="submit"
                  disabled={createMutation.isPending || title.trim() === ''}
                  style={{
                    background: 'var(--accent)',
                    color: 'var(--bg)',
                    padding: '4px 12px',
                    fontWeight: 700,
                    fontSize: 10,
                    letterSpacing: '0.08em',
                  }}
                >
                  CREATE
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCreating(false);
                    setTitle('');
                  }}
                  style={{ color: 'var(--ink-3)', fontSize: 10 }}
                >
                  CANCEL
                </button>
              </div>
            </form>
          </Panel>
        )}

        <Panel
          title="REF. PRICES"
          right={<span className="dim" style={{ fontSize: 10 }}>{currency}</span>}
          style={{ border: 0, borderTop: '1px solid var(--line)' }}
        >
          <div className="mono dim" style={{ fontSize: 11, lineHeight: 1.6 }}>
            Values use Scryfall daily feeds ({priceSourceLabel(currency)}). Win-rate
            and activity feeds are omitted until backed by simulation history.
          </div>
        </Panel>
      </div>

      {hover && (
        <HoverPreview
          name={hover.name}
          imageUri={hover.imageUri}
          x={hover.x}
          y={hover.y}
        />
      )}
    </div>
  );
};

function DeckPreview({
  deck,
  cards,
  manaSymbolStyle,
  currency,
  onHover,
  onClearHover,
}: {
  deck: Deck;
  cards: DeckCardWithCard[];
  manaSymbolStyle: 'letter' | 'dot' | 'wedge' | 'sq';
  currency: 'USD' | 'EUR';
  onHover: (name: string, imageUri: string | null, e: React.MouseEvent) => void;
  onClearHover: () => void;
}) {
  const md = cards.filter(c => !c.isSideboard);
  const top = [...md].sort((a, b) => b.quantity - a.quantity).slice(0, 6);
  const colors = deckColorIdentity(cards);

  return (
    <div style={{ padding: 12, borderBottom: '1px solid var(--line)' }}>
      <div className="mono uc dim" style={{ fontSize: 9, marginBottom: 6 }}>
        PREVIEW
      </div>
      <div className="sans" style={{ fontSize: 18, fontWeight: 700, marginBottom: 2 }}>
        {deck.attributes.title}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <ColorIdStrip colors={colors} manaSymbolStyle={manaSymbolStyle} />
        <span className="dim mono" style={{ fontSize: 10 }}>
          {deck.attributes.field_format}
        </span>
      </div>
      {deck.attributes.field_notes && (
        <div
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 11,
            color: 'var(--ink-2)',
            marginBottom: 12,
            lineHeight: 1.6,
            maxHeight: 72,
            overflow: 'hidden',
          }}
        >
          {notePreview(deck.attributes.field_notes)}
        </div>
      )}
      <div className="mono uc dim" style={{ fontSize: 9, marginBottom: 4 }}>
        KEY CARDS
      </div>
      {top.length === 0 ? (
        <div className="mono dim" style={{ fontSize: 11 }}>
          {cards.length === 0 ? 'Loading cards...' : 'No mainboard cards yet.'}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
          {top.map(slot => (
            <div
              key={slot.id}
              onMouseEnter={e =>
                onHover(slot.card.title, slot.card.field_image_uri, e)
              }
              onMouseMove={e =>
                onHover(slot.card.title, slot.card.field_image_uri, e)
              }
              onMouseLeave={onClearHover}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '3px 6px',
                fontFamily: 'var(--mono)',
                fontSize: 11,
                background: 'var(--bg-2)',
                borderLeft: '2px solid var(--accent)',
                cursor: 'crosshair',
              }}
            >
              <span className="tnum" style={{ width: 14, color: 'var(--accent)' }}>
                {slot.quantity}
              </span>
              <span
                style={{
                  flex: 1,
                  color: 'var(--ink)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {slot.card.title}
              </span>
              <ManaCost
                cost={slot.card.field_mana_cost}
                style={manaSymbolStyle}
                size={12}
              />
            </div>
          ))}
        </div>
      )}
      <div className="mono tnum dim" style={{ fontSize: 10, marginTop: 10 }}>
        MAIN {mainDeckCount(cards)} · VALUE{' '}
        {formatPriceInt(totalDeckPrice(cards, currency), currency)}
      </div>
    </div>
  );
}

export default DecksPage;
