import React, { useMemo } from 'react';
import Link from 'next/link';
import { slugify } from '../utils/slugify';
import { formatPrice, tradeValue, type Currency } from '../utils/prices';
import type { CollectionCard } from '../types/drupal';

interface TradeListProps {
  /** Collection rows; only rows with copies for trade are shown. */
  rows: CollectionCard[];
  currency: Currency;
  /** Saves a new trade count and/or binder location for a row. */
  onChange: (row: CollectionCard, quantityTrade: number, binderLocation: string) => void;
}

const inputStyle: React.CSSProperties = {
  padding: '2px 4px',
  color: '#000',
  background: '#fff',
  border: '1px solid #000',
};

/**
 * The trade binder: printings with copies marked for trade, sorted by binder
 * location so the list follows the binder.
 */
const TradeList: React.FC<TradeListProps> = ({ rows, currency, onChange }) => {
  const sorted = useMemo(
    () =>
      rows
        .filter(r => (r.attributes.field_quantity_trade ?? 0) > 0)
        .sort((a, b) => {
          const la = a.attributes.field_binder_location ?? '';
          const lb = b.attributes.field_binder_location ?? '';
          if (la !== lb) {
            // Rows without a location go last.
            if (la === '') return 1;
            if (lb === '') return -1;
            return la.localeCompare(lb, undefined, { numeric: true });
          }
          return (a.attributes.field_card_title ?? '').localeCompare(b.attributes.field_card_title ?? '');
        }),
    [rows],
  );

  const total = sorted.reduce((sum, r) => sum + tradeValue(r.attributes, currency), 0);
  const copies = sorted.reduce((sum, r) => sum + (r.attributes.field_quantity_trade ?? 0), 0);

  if (sorted.length === 0) {
    return (
      <p>
        Nothing is marked for trade yet. Use the Trade counter on a card in the All cards view,
        or on its collection page.
      </p>
    );
  }

  return (
    <div>
      <p style={{ marginTop: 0 }}>
        {copies} copies, {formatPrice(total, currency)} at current prices.
      </p>
      <table className="mono" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--line)' }}>
            <th style={{ padding: 4 }}>Card</th>
            <th style={{ padding: 4 }}>Printing</th>
            <th style={{ padding: 4 }}>Owned</th>
            <th style={{ padding: 4 }}>For trade</th>
            <th style={{ padding: 4 }}>Binder location</th>
            <th style={{ padding: 4, textAlign: 'right' }}>Value</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(row => {
            const a = row.attributes;
            const owned = (a.field_quantity_owned ?? 0) + (a.field_quantity_foil ?? 0);
            const trade = a.field_quantity_trade ?? 0;
            const location = a.field_binder_location ?? '';
            const title = a.field_card_title ?? '';
            return (
              <tr key={row.id} style={{ borderBottom: '1px solid var(--line)' }}>
                <td style={{ padding: 4 }}>
                  <Link href={`/collection/card/${slugify(title)}`} style={{ color: 'var(--ink)' }}>
                    {title}
                  </Link>
                </td>
                <td style={{ padding: 4 }}>
                  {a.field_set_name} #{a.field_collector_number}
                  {(a.field_quantity_foil ?? 0) > 0 ? ' (has foil)' : ''}
                </td>
                <td style={{ padding: 4 }}>{owned}</td>
                <td style={{ padding: 4, whiteSpace: 'nowrap' }}>
                  <button type="button" onClick={() => onChange(row, trade - 1, location)} style={{ width: 24, padding: 0 }}>
                    -
                  </button>{' '}
                  {trade}{' '}
                  <button
                    type="button"
                    onClick={() => onChange(row, trade + 1, location)}
                    disabled={trade >= owned}
                    style={{ width: 24, padding: 0 }}
                  >
                    +
                  </button>
                </td>
                <td style={{ padding: 4 }}>
                  <input
                    key={`${row.id}-${location}`}
                    type="text"
                    defaultValue={location}
                    placeholder="e.g. page 3, pocket 7"
                    onBlur={e => {
                      if (e.target.value !== location) onChange(row, trade, e.target.value);
                    }}
                    style={{ ...inputStyle, width: '100%' }}
                  />
                </td>
                <td style={{ padding: 4, textAlign: 'right' }}>
                  {formatPrice(tradeValue(a, currency), currency)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default TradeList;
