import type { MtgCardAttributes } from '../types/drupal';

export type Currency = 'USD' | 'EUR';

export function priceSourceLabel(currency: Currency): string {
  return currency === 'EUR' ? 'CARDMARKET TREND' : 'TCGPLAYER MARKET';
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
  if (raw == null || raw === '') {
    return null;
  }
  const n = Number.parseFloat(raw);
  return Number.isFinite(n) ? n : null;
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

export function totalDeckPrice(
  cards: Array<{ quantity: number; card: MtgCardAttributes; isSideboard?: boolean }>,
  currency: Currency,
  includeSideboard = false,
  foil = false,
): number {
  return cards.reduce((sum, slot) => {
    if (!includeSideboard && slot.isSideboard) {
      return sum;
    }
    const unit =
      (foil ? priceFor(slot.card, currency, true) : null) ??
      priceFor(slot.card, currency) ??
      0;
    return sum + unit * slot.quantity;
  }, 0);
}
