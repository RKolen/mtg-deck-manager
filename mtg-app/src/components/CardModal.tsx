import React, { useEffect } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { getOracleText } from '../utils/deckAnalysis';
import { slugify } from '../utils/slugify';
import { formatPrice, priceFor, type Currency } from '../utils/prices';
import { useTheme } from '../context/ThemeContext';
import { fetchTokenPrice } from '../services/drupalApi';

/** Tokens, emblems, game pieces and face-down reminder cards. */
export function isTokenType(typeLine: string | null | undefined): boolean {
  const type = typeLine ?? '';
  return /^(Token|Emblem|Dungeon|Card)\b/.test(type) || type === 'Creature';
}

type PriceFields = {
  field_price_usd: string | null;
  field_price_usd_foil: string | null;
  field_price_eur: string | null;
  field_price_eur_foil: string | null;
};

/**
 * Price in the chosen currency, or the other currency's price converted
 * (converted: true) when the printing has none in the chosen one.
 */
export function priceWithFallback(
  priced: PriceFields,
  currency: Currency,
  foil: boolean,
  usdToEur: number | null,
): { value: number | null; converted: boolean } {
  const own = priceFor(priced, currency, foil);
  if (own != null) {
    return { value: own, converted: false };
  }
  const raw = priceFor(priced, currency === 'EUR' ? 'USD' : 'EUR', foil);
  if (raw == null || usdToEur == null || usdToEur <= 0) {
    return { value: null, converted: false };
  }
  return { value: currency === 'EUR' ? raw * usdToEur : raw / usdToEur, converted: true };
}

export interface CardData {
  id: string;
  drupalId?: string;
  title?: string | null;
  field_mana_cost?: string | null;
  field_cmc?: number | null;
  field_type_line?: string | null;
  field_colors?: string[] | null;
  /** Plain string or Drupal text object `{ value, format, processed }`. */
  field_oracle_text?: string | { value?: string; format?: string | null; processed?: string } | null;
  field_scryfall_id?: string | null;
  field_image_uri?: string | null;
  field_is_mana_producer?: boolean | null;
  field_produced_mana?: string[] | null;
  field_legal_formats?: string[] | null;
  // Phase 9
  field_price_usd?: string | null;
  field_price_usd_foil?: string | null;
  field_price_eur?: string | null;
  field_price_eur_foil?: string | null;
  field_set_name?: string | null;
  field_rarity?: string | null;
}

interface CardModalProps {
  card: CardData;
  quantityOwned?: number;
  quantityFoil?: number;
  onClose: () => void;
  /** When set, shows editable regular/foil quantity controls. */
  onQuantityChange?: (owned: number, foil: number) => void;
}

const qtyInputStyle: React.CSSProperties = {
  width: 48,
  textAlign: 'center',
  padding: '2px 4px',
  color: '#000',
  background: '#fff',
  border: '1px solid #000',
};

const CardModal: React.FC<CardModalProps> = ({
  card,
  quantityOwned = 0,
  quantityFoil = 0,
  onClose,
  onQuantityChange,
}) => {
  // Close on Escape key.
  useEffect(() => {
    const handler = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const oracleText = getOracleText(card);
  const total = quantityOwned + quantityFoil;
  const { currency, usdToEur } = useTheme();
  const priced = {
    field_price_usd: card.field_price_usd ?? null,
    field_price_usd_foil: card.field_price_usd_foil ?? null,
    field_price_eur: card.field_price_eur ?? null,
    field_price_eur_foil: card.field_price_eur_foil ?? null,
  };
  const regular = priceWithFallback(priced, currency, false, usdToEur);
  const foil = priceWithFallback(priced, currency, true, usdToEur);

  // A token printing without any price: any printing with the same name,
  // stats and abilities works at the table, so show the cheapest of those.
  const needsTokenPrice = isTokenType(card.field_type_line) && regular.value == null && foil.value == null;
  const { data: tokenPrice } = useQuery({
    queryKey: ['tokenPrice', card.id],
    queryFn: () => fetchTokenPrice(card.id),
    enabled: needsTokenPrice && card.id !== '',
  });
  const anyPrinting = tokenPrice != null
    ? priceWithFallback(
      {
        field_price_eur: tokenPrice.priceEur != null ? String(tokenPrice.priceEur) : null,
        field_price_eur_foil: null,
        field_price_usd: tokenPrice.priceUsd != null ? String(tokenPrice.priceUsd) : null,
        field_price_usd_foil: null,
      },
      currency,
      false,
      usdToEur,
    )
    : null;

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
          background: 'var(--bg-1)',
          color: 'var(--ink)',
          border: '1px solid var(--line-2)',
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

        <div style={{ flex: 1, color: 'var(--ink)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <h2 style={{ margin: 0, color: 'var(--ink)' }}>{card.title}</h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              style={{
                background: 'none',
                border: 'none',
                fontSize: 20,
                cursor: 'pointer',
                color: 'var(--ink)',
              }}
            >
              x
            </button>
          </div>

          {card.title != null && card.title !== '' && (
            <p style={{ margin: '0.5rem 0 0.25rem' }}>
              <Link
                href={`/cards/${slugify(card.title)}${card.id ? `?printing=${card.id}` : ''}`}
                onClick={onClose}
                style={{ color: 'var(--accent)', fontSize: '0.9rem' }}
              >
                View all printings →
              </Link>
            </p>
          )}

          <p style={{ margin: '0.25rem 0', color: 'var(--ink)' }}>
            {card.field_mana_cost ?? ''}{' '}
            {card.field_cmc != null && `(CMC ${card.field_cmc})`}
          </p>

          {card.field_type_line != null && (
            <p style={{ margin: '0.25rem 0', fontStyle: 'italic', color: 'var(--ink)' }}>
              {card.field_type_line}
            </p>
          )}

          {oracleText !== '' && (
            <p
              style={{
                whiteSpace: 'pre-wrap',
                background: 'var(--bg-2)',
                color: 'var(--ink)',
                border: '1px solid var(--line)',
                padding: '0.5rem',
                borderRadius: 4,
                fontSize: '0.9rem',
              }}
            >
              {oracleText}
            </p>
          )}

          {card.field_colors != null && card.field_colors.length > 0 && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.85rem', color: 'var(--ink)' }}>
              <strong>Colors:</strong> {card.field_colors.join(', ')}
            </p>
          )}

          {card.field_is_mana_producer === true &&
            card.field_produced_mana != null &&
            card.field_produced_mana.length > 0 && (
              <p style={{ margin: '0.25rem 0', fontSize: '0.85rem', color: 'var(--ink)' }}>
                <strong>Produces:</strong> {card.field_produced_mana.join(', ')}
              </p>
            )}

          {(card.field_set_name || card.field_rarity) && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.85rem', color: 'var(--ink)' }}>
              {card.field_set_name}
              {card.field_rarity && ` · ${card.field_rarity.charAt(0).toUpperCase()}${card.field_rarity.slice(1)}`}
            </p>
          )}

          {(regular.value != null || foil.value != null) && (
            <p
              style={{ margin: '0.25rem 0', fontSize: '0.85rem', color: 'var(--ink)' }}
              title={regular.converted || foil.converted ? 'Converted from the other currency' : undefined}
            >
              {regular.value != null && (
                <><strong>{currency}:</strong> {regular.converted ? '≈ ' : ''}{formatPrice(regular.value, currency)}</>
              )}
              {regular.value != null && foil.value != null && ' · '}
              {foil.value != null && (
                <><strong>Foil:</strong> {foil.converted ? '≈ ' : ''}{formatPrice(foil.value, currency)}</>
              )}
            </p>
          )}
          {needsTokenPrice && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.85rem', color: 'var(--ink)' }}>
              No price for this printing.
              {anyPrinting?.value != null && (
                <>
                  {' '}Any printing: from {anyPrinting.converted ? '≈ ' : ''}{formatPrice(anyPrinting.value, currency)}
                  {tokenPrice?.card?.setCode
                    ? ` (${tokenPrice.card.setCode.toUpperCase()}${tokenPrice.card.collectorNumber ? ` #${tokenPrice.card.collectorNumber}` : ''})`
                    : ''}
                </>
              )}
            </p>
          )}

          <hr style={{ borderColor: 'var(--line)' }} />

          {onQuantityChange ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 64, fontSize: '0.85rem' }}>Regular</span>
                <button
                  type="button"
                  disabled={quantityOwned <= 0}
                  onClick={() => onQuantityChange(quantityOwned - 1, quantityFoil)}
                  style={{ width: 28, padding: 0 }}
                >
                  -
                </button>
                <input
                  type="number"
                  min={0}
                  value={quantityOwned}
                  onChange={e =>
                    onQuantityChange(Math.max(0, Number.parseInt(e.target.value, 10) || 0), quantityFoil)
                  }
                  style={qtyInputStyle}
                />
                <button
                  type="button"
                  onClick={() => onQuantityChange(quantityOwned + 1, quantityFoil)}
                  style={{ width: 28, padding: 0 }}
                >
                  +
                </button>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 64, fontSize: '0.85rem' }}>Foil</span>
                <button
                  type="button"
                  disabled={quantityFoil <= 0}
                  onClick={() => onQuantityChange(quantityOwned, quantityFoil - 1)}
                  style={{ width: 28, padding: 0 }}
                >
                  -
                </button>
                <input
                  type="number"
                  min={0}
                  value={quantityFoil}
                  onChange={e =>
                    onQuantityChange(quantityOwned, Math.max(0, Number.parseInt(e.target.value, 10) || 0))
                  }
                  style={qtyInputStyle}
                />
                <button
                  type="button"
                  onClick={() => onQuantityChange(quantityOwned, quantityFoil + 1)}
                  style={{ width: 28, padding: 0 }}
                >
                  +
                </button>
              </div>
              <p style={{ margin: 0, fontSize: '0.85rem' }}>
                Total: <strong>{total}</strong>
                {total > 0 && (
                  <span style={{ opacity: 0.85 }}>
                    {' '}
                    ({quantityOwned} regular + {quantityFoil} foil)
                  </span>
                )}
              </p>
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--ink)' }}>
              <strong>Regular:</strong> {quantityOwned}&ensp;
              <strong>Foil:</strong> {quantityFoil}&ensp;
              <strong>Total:</strong> {total}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default CardModal;
