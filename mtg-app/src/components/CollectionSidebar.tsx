import React from 'react';
import { formatPrice, type Currency } from '../utils/prices';

interface CollectionSidebarProps {
  totalCards: number;
  totalUnique: number;
  totalFoil: number;
  filtered: number;
  filteredUnique: number;
  estValue: number | null;
  currency: Currency;
}

const CollectionSidebar: React.FC<CollectionSidebarProps> = ({
  totalCards,
  totalUnique,
  totalFoil,
  filtered,
  filteredUnique,
  estValue,
  currency,
}) => (
  <aside
    className="summary-card"
    style={{
      padding: '1rem',
      minWidth: 160,
    }}
  >
    <h3 style={{ margin: '0 0 0.75rem', color: 'var(--ink)' }}>Collection</h3>
    <dl style={{ margin: 0, color: 'var(--ink)' }}>
      <dt style={{ color: 'var(--ink)' }}>Total cards</dt>
      <dd style={{ marginLeft: 0, fontWeight: 'bold', color: 'var(--ink)' }}>{totalCards}</dd>
      <dt style={{ color: 'var(--ink)' }}>Unique cards</dt>
      <dd style={{ marginLeft: 0, fontWeight: 'bold', color: 'var(--ink)' }}>{totalUnique}</dd>
      <dt style={{ color: 'var(--ink)' }}>Foil copies</dt>
      <dd style={{ marginLeft: 0, fontWeight: 'bold', color: 'var(--ink)' }}>{totalFoil}</dd>
      {estValue != null && (
        <>
          <dt style={{ color: 'var(--ink)' }}>Est. value ({currency})</dt>
          <dd style={{ marginLeft: 0, fontWeight: 'bold', color: 'var(--ink)' }}>
            {formatPrice(estValue, currency)}
          </dd>
        </>
      )}
    </dl>
    {filtered !== totalUnique && (
      <>
        <hr style={{ borderColor: 'var(--line)' }} />
        <dl style={{ margin: 0, fontSize: '0.85rem', color: 'var(--ink)' }}>
          <dt>Filtered shown</dt>
          <dd style={{ marginLeft: 0, fontWeight: 'bold' }}>{filteredUnique}</dd>
          <dt>Filtered copies</dt>
          <dd style={{ marginLeft: 0, fontWeight: 'bold' }}>{filtered}</dd>
        </dl>
      </>
    )}
  </aside>
);

export default CollectionSidebar;
