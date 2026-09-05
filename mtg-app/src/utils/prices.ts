import type { MtgCardAttributes } from '../types/drupal';

export type Currency = 'USD' | 'EUR';

export function priceSourceLabel(currency: Currency): string {
  return currency === 'EUR' ? 'CARDMARKET TREND' : 'TCGPLAYER MARKET';
}

function parsePrice(raw: string | number | null | undefined): number | null {
  if (raw == null || raw === '') {
    return null;
  }
  const n = typeof raw === 'number' ? raw : Number.parseFloat(raw);
  // Scryfall stores "no listing" as null; Drupal decimals may come through as 0.
  if (!Number.isFinite(n) || n <= 0) {
    return null;
  }
  return n;
}

export function priceFor(
  card: Pick<
    MtgCardAttributes,
    'field_price_usd' | 'field_price_usd_foil' | 'field_price_eur' | 'field_price_eur_foil'
  >,
  currency: Currency,
  foil = false,
): number | null {
  const raw =
    currency === 'EUR'
      ? foil
        ? card.field_price_eur_foil
        : card.field_price_eur
      : foil
        ? card.field_price_usd_foil
        : card.field_price_usd;
  return parsePrice(raw);
}

export function formatPrice(value: number | null | undefined, currency: Currency): string {
  if (value == null || !Number.isFinite(value)) {
    return '--';
  }
  const symbol = currency === 'EUR' ? 'EUR ' : '$';
  return `${symbol}${value.toFixed(2)}`;
}

export function formatPriceInt(value: number | null | undefined, currency: Currency): string {
  if (value == null || !Number.isFinite(value)) {
    return '--';
  }
  const symbol = currency === 'EUR' ? 'EUR ' : '$';
  return `${symbol}${Math.round(value)}`;
}

/**
 * Unit price for a deck slot. Foil uses foil listings first and only then
 * regular; regular never falls back to foil (serialized foil can dwarf it).
 */
export function slotUnitPrice(
  card: Pick<
    MtgCardAttributes,
    'field_price_usd' | 'field_price_usd_foil' | 'field_price_eur' | 'field_price_eur_foil'
  >,
  currency: Currency,
  foil = false,
): number {
  const other: Currency = currency === 'EUR' ? 'USD' : 'EUR';
  if (foil) {
    return (
      priceFor(card, currency, true) ??
      priceFor(card, other, true) ??
      priceFor(card, currency, false) ??
      priceFor(card, other, false) ??
      0
    );
  }
  return priceFor(card, currency, false) ?? priceFor(card, other, false) ?? 0;
}

export function totalDeckPrice(
  cards: Array<{
    quantity: number;
    card: MtgCardAttributes;
    isSideboard?: boolean;
    isFoil?: boolean;
  }>,
  currency: Currency,
  includeSideboard = false,
): number {
  return cards.reduce((sum, slot) => {
    if (!includeSideboard && slot.isSideboard) {
      return sum;
    }
    return sum + slotUnitPrice(slot.card, currency, Boolean(slot.isFoil)) * slot.quantity;
  }, 0);
}
