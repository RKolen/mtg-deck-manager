import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchCardSets } from '../services/cardSearch';
import { fetchDecks } from '../services/drupalApi';
import type { MtgColor } from '../utils/deckAnalysis';

export interface FilterState {
  name: string;
  colors: Set<MtgColor>;
  type: string;
  maxCmc: number | null;
  legalIn: string;
  oracleText: string;
  rarity: string;
  /** Lowercase Scryfall set codes. */
  setCodes: string[];
  /** When true, exclude the selected sets instead of including only them. */
  setExclude: boolean;
  /** Deck UUIDs. */
  deckIds: string[];
  /** When true, exclude cards in the selected decks. */
  deckExclude: boolean;
}

interface CardFilterProps {
  filter: FilterState;
  onChange: (next: FilterState) => void;
}

export const EMPTY_FILTER: FilterState = {
  name: '',
  colors: new Set(),
  type: 'All',
  maxCmc: null,
  legalIn: '',
  oracleText: '',
  rarity: '',
  setCodes: [],
  setExclude: false,
  deckIds: [],
  deckExclude: false,
};

const COLORS: { value: MtgColor; label: string; symbol: string }[] = [
  { value: 'W', label: 'White', symbol: 'W' },
  { value: 'U', label: 'Blue', symbol: 'U' },
  { value: 'B', label: 'Black', symbol: 'B' },
  { value: 'R', label: 'Red', symbol: 'R' },
  { value: 'G', label: 'Green', symbol: 'G' },
];

const FORMATS = [
  '',
  'standard',
  'pioneer',
  'modern',
  'legacy',
  'vintage',
  'pauper',
  'commander',
  'historic',
  'explorer',
  'timeless',
  'alchemy',
  'brawl',
  'standardbrawl',
  'paupercommander',
  'oathbreaker',
  'predh',
  'premodern',
  'oldschool',
  'penny',
  'duel',
  'gladiator',
];

function legalFormatLabel(key: string): string {
  const labels: Record<string, string> = {
    '': 'Any format',
    standardbrawl: 'Standard Brawl',
    paupercommander: 'Pauper Commander',
    oldschool: 'Old School',
    predh: 'Predh',
  };
  return labels[key] ?? key.charAt(0).toUpperCase() + key.slice(1);
}

const TYPES = [
  'All',
  'Basic Land',
  'Land',
  'Creature',
  'Artifact',
  'Enchantment',
  'Planeswalker',
  'Instant',
  'Sorcery',
];

const fieldStyle: React.CSSProperties = {
  width: '100%',
  marginTop: 4,
  color: '#000',
  background: '#fff',
  border: '1px solid #000',
  padding: '4px 6px',
};

const CardFilter: React.FC<CardFilterProps> = ({ filter, onChange }) => {
  const { data: setOptions = [] } = useQuery({
    queryKey: ['cardSets', 'all'],
    queryFn: () => fetchCardSets('', 1000),
    staleTime: 10 * 60_000,
  });

  const { data: decks = [] } = useQuery({
    queryKey: ['decks'],
    queryFn: fetchDecks,
    staleTime: 60_000,
  });

  const selectedSetMeta = useMemo(() => {
    const map = new Map(setOptions.map(s => [s.code, s]));
    return filter.setCodes.map(code => map.get(code) ?? { code, name: code.toUpperCase(), count: 0 });
  }, [filter.setCodes, setOptions]);

  const availableSets = useMemo(
    () => setOptions.filter(s => !filter.setCodes.includes(s.code)),
    [setOptions, filter.setCodes],
  );

  const selectedDecks = useMemo(
    () => decks.filter(d => filter.deckIds.includes(d.id)),
    [decks, filter.deckIds],
  );

  const availableDecks = useMemo(
    () => decks.filter(d => !filter.deckIds.includes(d.id)),
    [decks, filter.deckIds],
  );

  function toggleColor(color: MtgColor): void {
    const next = new Set(filter.colors);
    if (next.has(color)) {
      next.delete(color);
    } else {
      next.add(color);
    }
    onChange({ ...filter, colors: next });
  }

  function addSet(code: string): void {
    const normalized = code.toLowerCase();
    if (!normalized || filter.setCodes.includes(normalized)) {
      return;
    }
    onChange({ ...filter, setCodes: [...filter.setCodes, normalized] });
  }

  function removeSet(code: string): void {
    onChange({
      ...filter,
      setCodes: filter.setCodes.filter(c => c !== code),
    });
  }

  function addDeck(id: string): void {
    if (!id || filter.deckIds.includes(id)) {
      return;
    }
    onChange({ ...filter, deckIds: [...filter.deckIds, id] });
  }

  function removeDeck(id: string): void {
    onChange({
      ...filter,
      deckIds: filter.deckIds.filter(d => d !== id),
    });
  }

  return (
    <aside
      style={{
        padding: '1rem',
        borderRight: '1px solid var(--line)',
        minWidth: 180,
        color: 'var(--ink)',
        background: 'var(--bg-1)',
        overflow: 'auto',
      }}
    >
      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="card-search" style={{ color: 'var(--ink)' }}>
          <strong>Name</strong>
        </label>
        <br />
        <input
          id="card-search"
          type="search"
          value={filter.name}
          onChange={e => onChange({ ...filter, name: e.target.value })}
          placeholder="Card name…"
          style={fieldStyle}
        />
        <div style={{ fontSize: 10, color: 'var(--ink)', marginTop: 4, opacity: 0.85 }}>
          Searches card title only
        </div>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <strong style={{ color: 'var(--ink)' }}>Color</strong>
        <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
          {COLORS.map(c => (
            <button
              key={c.value}
              type="button"
              onClick={() => toggleColor(c.value)}
              title={c.label}
              style={{
                width: 32,
                height: 32,
                fontWeight: 'bold',
                cursor: 'pointer',
                border: filter.colors.has(c.value) ? '2px solid #000' : '1px solid #000',
                borderRadius: 4,
                background: filter.colors.has(c.value) ? '#e8e8e8' : '#fff',
                color: '#000',
              }}
            >
              {c.symbol}
            </button>
          ))}
        </div>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="oracle-text" style={{ color: 'var(--ink)' }}>
          <strong>Oracle Text</strong>
        </label>
        <br />
        <input
          id="oracle-text"
          type="search"
          value={filter.oracleText}
          onChange={e => onChange({ ...filter, oracleText: e.target.value })}
          placeholder="Oracle text…"
          style={fieldStyle}
        />
        <div style={{ fontSize: 10, color: 'var(--ink)', marginTop: 4, opacity: 0.85 }}>
          Searches rules text only
        </div>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="type-select" style={{ color: 'var(--ink)' }}>
          <strong>Type</strong>
        </label>
        <br />
        <select
          id="type-select"
          value={filter.type}
          onChange={e => onChange({ ...filter, type: e.target.value })}
          style={fieldStyle}
        >
          {TYPES.map(t => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="format-select" style={{ color: 'var(--ink)' }}>
          <strong>Legal In</strong>
        </label>
        <br />
        <select
          id="format-select"
          value={filter.legalIn}
          onChange={e => onChange({ ...filter, legalIn: e.target.value })}
          style={fieldStyle}
        >
          {FORMATS.map(f => (
            <option key={f} value={f}>
              {legalFormatLabel(f)}
            </option>
          ))}
        </select>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="cmc-select" style={{ color: 'var(--ink)' }}>
          <strong>Max CMC</strong>
        </label>
        <br />
        <select
          id="cmc-select"
          value={filter.maxCmc ?? ''}
          onChange={e =>
            onChange({
              ...filter,
              maxCmc: e.target.value === '' ? null : Number(e.target.value),
            })
          }
          style={fieldStyle}
        >
          <option value="">Any</option>
          {[0, 1, 2, 3, 4, 5, 6, 7].map(n => (
            <option key={n} value={n}>
              {n <= 6 ? String(n) : '7+'}
            </option>
          ))}
        </select>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="rarity-select" style={{ color: 'var(--ink)' }}>
          <strong>Rarity</strong>
        </label>
        <br />
        <select
          id="rarity-select"
          value={filter.rarity}
          onChange={e => onChange({ ...filter, rarity: e.target.value })}
          style={fieldStyle}
        >
          <option value="">Any</option>
          <option value="common">Common</option>
          <option value="uncommon">Uncommon</option>
          <option value="rare">Rare</option>
          <option value="mythic">Mythic</option>
        </select>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <strong style={{ color: 'var(--ink)' }}>Set</strong>
        <div
          style={{
            display: 'flex',
            gap: 6,
            marginTop: 4,
            marginBottom: 6,
          }}
        >
          <button
            type="button"
            onClick={() => onChange({ ...filter, setExclude: false })}
            style={{
              flex: 1,
              fontSize: 11,
              padding: '4px 6px',
              border: filter.setExclude ? '1px solid #000' : '2px solid #000',
              background: filter.setExclude ? '#fff' : '#e8e8e8',
              color: '#000',
              cursor: 'pointer',
            }}
          >
            Include
          </button>
          <button
            type="button"
            onClick={() => onChange({ ...filter, setExclude: true })}
            style={{
              flex: 1,
              fontSize: 11,
              padding: '4px 6px',
              border: filter.setExclude ? '2px solid #000' : '1px solid #000',
              background: filter.setExclude ? '#e8e8e8' : '#fff',
              color: '#000',
              cursor: 'pointer',
            }}
          >
            Exclude
          </button>
        </div>
        <label htmlFor="set-select" style={{ color: 'var(--ink)', fontSize: 11 }}>
          MTG Set
        </label>
        <select
          id="set-select"
          value=""
          onChange={e => {
            if (e.target.value) {
              addSet(e.target.value);
            }
          }}
          style={fieldStyle}
        >
          <option value="">Select a set…</option>
          {availableSets.map(s => (
            <option key={s.code} value={s.code}>
              {s.name}
            </option>
          ))}
        </select>
        {selectedSetMeta.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
            {selectedSetMeta.map(s => (
              <button
                key={s.code}
                type="button"
                onClick={() => removeSet(s.code)}
                title={`Remove ${s.name}`}
                style={{
                  fontSize: 11,
                  padding: '4px 6px',
                  border: '1px solid #000',
                  borderRadius: 3,
                  background: '#fff',
                  color: '#000',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <strong>{s.name}</strong>
                <span> ×</span>
              </button>
            ))}
          </div>
        )}
        <div style={{ fontSize: 10, color: 'var(--ink)', marginTop: 4, opacity: 0.85 }}>
          {filter.setCodes.length === 0
            ? 'Pick from MTG Set taxonomy'
            : filter.setExclude
              ? 'Hiding selected sets'
              : 'Only selected sets'}
        </div>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <strong style={{ color: 'var(--ink)' }}>Deck</strong>
        <div
          style={{
            display: 'flex',
            gap: 6,
            marginTop: 4,
            marginBottom: 6,
          }}
        >
          <button
            type="button"
            onClick={() => onChange({ ...filter, deckExclude: false })}
            style={{
              flex: 1,
              fontSize: 11,
              padding: '4px 6px',
              border: filter.deckExclude ? '1px solid #000' : '2px solid #000',
              background: filter.deckExclude ? '#fff' : '#e8e8e8',
              color: '#000',
              cursor: 'pointer',
            }}
          >
            Include
          </button>
          <button
            type="button"
            onClick={() => onChange({ ...filter, deckExclude: true })}
            style={{
              flex: 1,
              fontSize: 11,
              padding: '4px 6px',
              border: filter.deckExclude ? '2px solid #000' : '1px solid #000',
              background: filter.deckExclude ? '#e8e8e8' : '#fff',
              color: '#000',
              cursor: 'pointer',
            }}
          >
            Exclude
          </button>
        </div>
        <label htmlFor="deck-select" style={{ color: 'var(--ink)', fontSize: 11 }}>
          Your decks
        </label>
        <select
          id="deck-select"
          value=""
          onChange={e => {
            if (e.target.value) {
              addDeck(e.target.value);
            }
          }}
          style={fieldStyle}
        >
          <option value="">Select a deck…</option>
          {availableDecks.map(d => (
            <option key={d.id} value={d.id}>
              {d.attributes.title}
              {d.attributes.field_format ? ` (${d.attributes.field_format})` : ''}
            </option>
          ))}
        </select>
        {selectedDecks.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
            {selectedDecks.map(d => (
              <button
                key={d.id}
                type="button"
                onClick={() => removeDeck(d.id)}
                title={`Remove ${d.attributes.title}`}
                style={{
                  fontSize: 11,
                  padding: '4px 6px',
                  border: '1px solid #000',
                  borderRadius: 3,
                  background: '#fff',
                  color: '#000',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <strong>{d.attributes.title}</strong>
                <span> ×</span>
              </button>
            ))}
          </div>
        )}
        <div style={{ fontSize: 10, color: 'var(--ink)', marginTop: 4, opacity: 0.85 }}>
          {filter.deckIds.length === 0
            ? 'Filter catalogue by deck membership'
            : filter.deckExclude
              ? 'Hiding cards in selected decks'
              : 'Only cards in selected decks'}
        </div>
      </div>

      <button
        type="button"
        onClick={() => onChange({ ...EMPTY_FILTER, colors: new Set() })}
        style={{ width: '100%', padding: '6px 8px' }}
      >
        Clear filters
      </button>
    </aside>
  );
};

export default CardFilter;
