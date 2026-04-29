import React, { useEffect } from 'react';

export interface CardData {
  id: string;
  drupalId?: string;
  title?: string | null;
  field_mana_cost?: string | null;
  field_cmc?: number | null;
  field_type_line?: string | null;
  field_colors?: string[] | null;
  field_oracle_text?: string | null;
  field_scryfall_id?: string | null;
  field_image_uri?: string | null;
  field_is_mana_producer?: boolean | null;
  field_produced_mana?: string[] | null;
  field_legal_formats?: string[] | null;
}

interface CardModalProps {
  card: CardData;
  quantityOwned?: number;
  quantityFoil?: number;
  onClose: () => void;
}

const CardModal: React.FC<CardModalProps> = ({
  card,
  quantityOwned = 0,
  quantityFoil = 0,
  onClose,
}) => {
  // Close on Escape key.
  useEffect(() => {
    const handler = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={card.title ?? 'Card detail'}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={e => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 8,
          padding: '1.5rem',
          maxWidth: 560,
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          display: 'flex',
          gap: '1.5rem',
        }}
      >
        {card.field_image_uri != null && (
          <img
            src={card.field_image_uri}
            alt={card.title ?? ''}
            style={{ width: 200, borderRadius: 8, alignSelf: 'flex-start' }}
          />
        )}

        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <h2 style={{ margin: 0 }}>{card.title}</h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer' }}
            >
              x
            </button>
          </div>

          <p style={{ margin: '0.25rem 0', color: '#555' }}>
            {card.field_mana_cost ?? ''}{' '}
            {card.field_cmc != null && `(CMC ${card.field_cmc})`}
          </p>

          {card.field_type_line != null && (
            <p style={{ margin: '0.25rem 0', fontStyle: 'italic' }}>
              {card.field_type_line}
            </p>
          )}

          {card.field_oracle_text != null && (
            <p
              style={{
                whiteSpace: 'pre-wrap',
                background: '#f5f5f0',
                padding: '0.5rem',
                borderRadius: 4,
                fontSize: '0.9rem',
              }}
            >
              {card.field_oracle_text}
            </p>
          )}

          {card.field_colors != null && card.field_colors.length > 0 && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.85rem' }}>
              <strong>Colors:</strong> {card.field_colors.join(', ')}
            </p>
          )}

          {card.field_is_mana_producer === true &&
            card.field_produced_mana != null &&
            card.field_produced_mana.length > 0 && (
              <p style={{ margin: '0.25rem 0', fontSize: '0.85rem' }}>
                <strong>Produces:</strong> {card.field_produced_mana.join(', ')}
              </p>
            )}

          <hr />
          <p style={{ margin: 0, fontSize: '0.9rem' }}>
            <strong>Owned:</strong> {quantityOwned}&ensp;
            <strong>Foil:</strong> {quantityFoil}
          </p>
        </div>
      </div>
    </div>
  );
};

export default CardModal;
