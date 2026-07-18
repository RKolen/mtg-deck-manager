import React from 'react';

interface CollectionSidebarProps {
  totalCards: number;
  totalUnique: number;
  totalFoil: number;
  filtered: number;
  filteredUnique: number;
  estValue: number | null;
}

const CollectionSidebar: React.FC<CollectionSidebarProps> = ({
  totalCards,
  totalUnique,
  totalFoil,
  filtered,
  filteredUnique,
  estValue,
}) => (
  <aside
    style={{
      padding: '1rem',
      background: '#f5f5f0',
      borderRadius: 4,
      minWidth: 160,
      color: '#000',
    }}
  >
    <h3 style={{ margin: '0 0 0.75rem', color: '#000' }}>Collection</h3>
    <dl style={{ margin: 0, color: '#000' }}>
      <dt>Total cards</dt>
      <dd style={{ marginLeft: 0, fontWeight: 'bold', color: '#000' }}>{totalCards}</dd>
      <dt>Unique cards</dt>
      <dd style={{ marginLeft: 0, fontWeight: 'bold', color: '#000' }}>{totalUnique}</dd>
      <dt>Foil copies</dt>
      <dd style={{ marginLeft: 0, fontWeight: 'bold', color: '#000' }}>{totalFoil}</dd>
      {estValue != null && (
        <>
          <dt>Est. value (USD)</dt>
          <dd style={{ marginLeft: 0, fontWeight: 'bold', color: '#000' }}>${estValue.toFixed(2)}</dd>
        </>
      )}
    </dl>
    {(filtered !== totalUnique) && (
      <>
        <hr />
        <dl style={{ margin: 0, fontSize: '0.85rem' }}>
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
