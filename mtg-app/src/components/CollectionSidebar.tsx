import React from 'react';

interface CollectionSidebarProps {
  totalCards: number;
  totalUnique: number;
  totalFoil: number;
  filtered: number;
  filteredUnique: number;
}

const CollectionSidebar: React.FC<CollectionSidebarProps> = ({
  totalCards,
  totalUnique,
  totalFoil,
  filtered,
  filteredUnique,
}) => (
  <aside
    style={{
      padding: '1rem',
      background: '#f5f5f0',
      borderRadius: 4,
      minWidth: 160,
    }}
  >
    <h3 style={{ margin: '0 0 0.75rem' }}>Collection</h3>
    <dl style={{ margin: 0 }}>
      <dt>Total cards</dt>
      <dd style={{ marginLeft: 0, fontWeight: 'bold' }}>{totalCards}</dd>
      <dt>Unique cards</dt>
      <dd style={{ marginLeft: 0, fontWeight: 'bold' }}>{totalUnique}</dd>
      <dt>Foil copies</dt>
      <dd style={{ marginLeft: 0, fontWeight: 'bold' }}>{totalFoil}</dd>
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
