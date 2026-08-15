import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchCollectionCardByCardId } from '../services/drupalApi';
import type { MtgCardAttributes } from '../types/drupal';
import { priceFor, formatPrice, type Currency } from '../utils/prices';

export type CollectionSwapMode = 'replace' | 'add';

export interface PrintingSwapTarget {
  id: string;
  attributes: MtgCardAttributes;
}

interface PrintingSwapDialogProps {
  current: PrintingSwapTarget;
  next: PrintingSwapTarget;
  currency: Currency;
  onCancel: () => void;
  onConfirm: (mode: CollectionSwapMode, foil: boolean) => void;
  isSaving: boolean;
  error: string | null;
}

function setLabel(card: PrintingSwapTarget): string {
  const a = card.attributes;
  const set = a.field_set_name ?? a.field_set_code?.toUpperCase() ?? 'Unknown set';
  const code = (a.field_set_code ?? '').toUpperCase();
  const num = a.field_collector_number ? ` #${a.field_collector_number}` : '';
  return code !== '' ? `${set} (${code}${num})` : set;
}

function collectionSummary(
  owned: number | undefined,
  foil: number | undefined,
): string {
  if (owned == null && foil == null) {
    return 'Checking collection...';
  }
  const o = owned ?? 0;
  const f = foil ?? 0;
  if (o + f < 1) {
    return 'Not in your collection yet.';
  }
  const parts: string[] = [];
  if (o > 0) {
    parts.push(`${o} regular`);
  }
  if (f > 0) {
    parts.push(`${f} foil`);
  }
  return `Already in collection (${parts.join(', ')}).`;
}

const PrintingSwapDialog: React.FC<PrintingSwapDialogProps> = ({
  current,
  next,
  currency,
  onCancel,
  onConfirm,
  isSaving,
  error,
}) => {
  const { data: currentCol } = useQuery({
    queryKey: ['collectionByCard', current.id],
    queryFn: () => fetchCollectionCardByCardId(current.id),
  });
  const { data: nextCol } = useQuery({
    queryKey: ['collectionByCard', next.id],
    queryFn: () => fetchCollectionCardByCardId(next.id),
  });

  const currentOwned = currentCol?.attributes.field_quantity_owned ?? 0;
  const currentFoil = currentCol?.attributes.field_quantity_foil ?? 0;
  const nextOwned = nextCol?.attributes.field_quantity_owned ?? 0;
  const nextFoilQty = nextCol?.attributes.field_quantity_foil ?? 0;
  const currentInCollection = currentOwned + currentFoil > 0;
  const nextInCollection = nextOwned + nextFoilQty > 0;
  const hasFoilPrice = priceFor(next.attributes, currency, true) != null;

  const [mode, setMode] = useState<CollectionSwapMode>(
    currentInCollection ? 'replace' : 'add',
  );
  const [foil, setFoil] = useState(currentFoil > 0 && currentOwned < 1);

  useEffect(() => {
    const handler = (e: KeyboardEvent): void => {
      if (e.key === 'Escape' && !isSaving) {
        onCancel();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isSaving, onCancel]);

  useEffect(() => {
    setMode(currentInCollection ? 'replace' : 'add');
  }, [currentInCollection, next.id]);

  useEffect(() => {
    setFoil(currentFoil > 0 && currentOwned < 1);
  }, [currentFoil, currentOwned, next.id]);

  const foilPrice = priceFor(next.attributes, currency, true);
  const regularPrice = priceFor(next.attributes, currency);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="printing-swap-title"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: 16,
      }}
      onClick={e => {
        if (e.target === e.currentTarget && !isSaving) {
          onCancel();
        }
      }}
    >
      <div
        style={{
          background: 'var(--bg-1)',
          color: 'var(--ink)',
          border: '1px solid var(--line-2)',
          borderRadius: 8,
          padding: '1.25rem 1.4rem',
          maxWidth: 460,
          width: '100%',
        }}
      >
        <h2 id="printing-swap-title" style={{ margin: '0 0 0.75rem', fontSize: '1.05rem' }}>
          Use this printing in the deck?
        </h2>
        <p style={{ margin: '0 0 0.85rem', fontSize: 13, lineHeight: 1.45 }}>
          Switch from <strong>{setLabel(current)}</strong> to{' '}
          <strong>{setLabel(next)}</strong>
          {regularPrice != null && (
            <>
              {' '}
              ({formatPrice(regularPrice, currency)}
              {foilPrice != null && foilPrice !== regularPrice && (
                <> · foil {formatPrice(foilPrice, currency)}</>
              )}
              )
            </>
          )}
          .
        </p>

        <p style={{ margin: '0 0 0.35rem', fontSize: 12, opacity: 0.9 }}>
          Current: {collectionSummary(
            currentCol === undefined ? undefined : currentOwned,
            currentCol === undefined ? undefined : currentFoil,
          )}
        </p>
        <p style={{ margin: '0 0 1rem', fontSize: 12, opacity: 0.9 }}>
          Selected: {collectionSummary(
            nextCol === undefined ? undefined : nextOwned,
            nextCol === undefined ? undefined : nextFoilQty,
          )}
        </p>

        <fieldset style={{ border: '1px solid var(--line)', borderRadius: 6, padding: '0.65rem 0.75rem', margin: '0 0 0.85rem' }}>
          <legend style={{ padding: '0 4px', fontSize: 12 }}>Collection</legend>
          <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 8, cursor: 'pointer' }}>
            <input
              type="radio"
              name="collectionMode"
              checked={mode === 'replace'}
              onChange={() => setMode('replace')}
              disabled={isSaving}
            />
            <span>
              <strong>Replace collection card</strong>
              <span style={{ display: 'block', opacity: 0.85, fontSize: 12 }}>
                Move this deck&apos;s copies from the old printing to the new one.
              </span>
            </span>
          </label>
          <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', cursor: 'pointer' }}>
            <input
              type="radio"
              name="collectionMode"
              checked={mode === 'add'}
              onChange={() => setMode('add')}
              disabled={isSaving}
            />
            <span>
              <strong>Add collection card</strong>
              <span style={{ display: 'block', opacity: 0.85, fontSize: 12 }}>
                {nextInCollection
                  ? 'Keep the old printing. Deck uses the new one (already owned).'
                  : 'Keep the old printing and add this one to the collection.'}
              </span>
            </span>
          </label>
        </fieldset>

        <label
          style={{
            display: 'flex',
            gap: 8,
            alignItems: 'center',
            marginBottom: '1rem',
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          <input
            type="checkbox"
            checked={foil}
            onChange={e => setFoil(e.target.checked)}
            disabled={isSaving}
          />
          These copies are foil
          {hasFoilPrice && foilPrice != null && (
            <span style={{ opacity: 0.85 }}>
              ({formatPrice(foilPrice, currency)})
            </span>
          )}
        </label>

        {error != null && error !== '' && (
          <p style={{ color: 'var(--neg)', margin: '0 0 0.75rem', fontSize: 13 }}>{error}</p>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button type="button" onClick={onCancel} disabled={isSaving}>
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(mode, foil)}
            disabled={isSaving}
            style={{ fontWeight: 700 }}
          >
            {isSaving ? 'Updating...' : 'Update deck'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PrintingSwapDialog;
