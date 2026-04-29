import React from 'react';
import type { MtgColor } from '../utils/deckAnalysis';

export interface FilterState {
  name: string;
  colors: Set<MtgColor>;
  type: string;
  maxCmc: number | null;
}

interface CardFilterProps {
  filter: FilterState;
  onChange: (next: FilterState) => void;
}

const COLORS: { value: MtgColor; label: string; symbol: string }[] = [
  { value: 'W', label: 'White', symbol: 'W' },
  { value: 'U', label: 'Blue', symbol: 'U' },
  { value: 'B', label: 'Black', symbol: 'B' },
  { value: 'R', label: 'Red', symbol: 'R' },
  { value: 'G', label: 'Green', symbol: 'G' },
];

const TYPES = [
  'All',
  'Land',
  'Creature',
  'Artifact',
  'Enchantment',
  'Planeswalker',
  'Instant',
  'Sorcery',
];

const CardFilter: React.FC<CardFilterProps> = ({ filter, onChange }) => {
  function toggleColor(color: MtgColor): void {
    const next = new Set(filter.colors);
    if (next.has(color)) {
      next.delete(color);
    } else {
      next.add(color);
    }
    onChange({ ...filter, colors: next });
  }

  return (
    <aside style={{ padding: '1rem', borderRight: '1px solid #ccc', minWidth: 180 }}>
      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="card-search">
          <strong>Name</strong>
        </label>
        <br />
        <input
          id="card-search"
          type="search"
          value={filter.name}
          onChange={e => onChange({ ...filter, name: e.target.value })}
          placeholder="Search..."
          style={{ width: '100%', marginTop: 4 }}
        />
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <strong>Color</strong>
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
                border: filter.colors.has(c.value)
                  ? '2px solid #333'
                  : '1px solid #aaa',
                borderRadius: 4,
                background: filter.colors.has(c.value) ? '#e8e0d0' : '#f5f5f5',
              }}
            >
              {c.symbol}
            </button>
          ))}
        </div>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="type-select">
          <strong>Type</strong>
        </label>
        <br />
        <select
          id="type-select"
          value={filter.type}
          onChange={e => onChange({ ...filter, type: e.target.value })}
          style={{ width: '100%', marginTop: 4 }}
        >
          {TYPES.map(t => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="cmc-select">
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
          style={{ width: '100%', marginTop: 4 }}
        >
          <option value="">Any</option>
          {[0, 1, 2, 3, 4, 5, 6, 7].map(n => (
            <option key={n} value={n}>
              {n <= 6 ? String(n) : '7+'}
            </option>
          ))}
        </select>
      </div>

      <button
        type="button"
        onClick={() =>
          onChange({ name: '', colors: new Set(), type: 'All', maxCmc: null })
        }
        style={{ width: '100%' }}
      >
        Clear filters
      </button>
    </aside>
  );
};

export default CardFilter;
