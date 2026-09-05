import React from 'react';

export type ArtFilter = 'all' | 'standard' | 'full';

export interface PrintingFilterValue {
  query: string;
  art: ArtFilter;
}

export const EMPTY_PRINTING_FILTER: PrintingFilterValue = {
  query: '',
  art: 'all',
};

type ArtFields = {
  field_full_art?: boolean | null;
  field_border_color?: string | null;
  field_set_code?: string | null;
  field_set_name?: string | null;
  field_collector_number?: string | null;
};

export function isFullArtPrinting(card: ArtFields): boolean {
  if (card.field_full_art) {
    return true;
  }
  return (card.field_border_color ?? '').toLowerCase() === 'borderless';
}

export function matchesPrintingFilter(
  card: ArtFields,
  filter: PrintingFilterValue,
): boolean {
  if (filter.art === 'full' && !isFullArtPrinting(card)) {
    return false;
  }
  if (filter.art === 'standard' && isFullArtPrinting(card)) {
    return false;
  }
  const raw = filter.query.trim().toLowerCase();
  if (raw === '') {
    return true;
  }
  const code = (card.field_set_code ?? '').toLowerCase();
  const name = (card.field_set_name ?? '').toLowerCase();
  const collector = (card.field_collector_number ?? '').toLowerCase();
  const hashed = collector === '' ? '' : `#${collector}`;
  const bare = raw.replace(/^#/, '');
  if (raw.startsWith('#') || /^\d+$/.test(raw)) {
    return collector === bare || collector.startsWith(bare) || hashed.includes(raw);
  }
  // Short tokens with a letter are set codes, so "ons" matches Onslaught
  // and not names that only contain those letters.
  if (/^(?=[a-z0-9]{2,5}$)(?=.*[a-z])[a-z0-9]+$/.test(raw)) {
    return code === raw || code.startsWith(raw);
  }
  return name.includes(raw) || code.includes(raw) || collector.includes(bare);
}

interface PrintingFilterProps {
  value: PrintingFilterValue;
  onChange: (next: PrintingFilterValue) => void;
  extra?: React.ReactNode;
}

const ART_OPTIONS: { id: ArtFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'standard', label: 'Standard' },
  { id: 'full', label: 'Full art' },
];

const PrintingFilter: React.FC<PrintingFilterProps> = ({ value, onChange, extra }) => {
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8,
        alignItems: 'center',
        marginBottom: '0.75rem',
      }}
    >
      <input
        type="search"
        value={value.query}
        onChange={e => onChange({ ...value, query: e.target.value })}
        placeholder="Set code, name, or 237"
        aria-label="Filter printings by set"
        style={{ flex: '1 1 180px', minWidth: 140 }}
      />
      <div role="group" aria-label="Art" style={{ display: 'flex', gap: 4 }}>
        {ART_OPTIONS.map(opt => {
          const active = value.art === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              aria-pressed={active}
              onClick={() => onChange({ ...value, art: opt.id })}
              style={{
                fontSize: 12,
                fontWeight: active ? 700 : 400,
                border: active ? '1px solid var(--ink)' : '1px solid var(--line)',
                background: active ? 'var(--bg-2)' : 'transparent',
                color: 'var(--ink)',
                padding: '0.25rem 0.55rem',
              }}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      {extra}
    </div>
  );
};

export default PrintingFilter;
