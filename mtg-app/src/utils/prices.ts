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
  const other: Currency = currency === 'EUR' ? 'USD' : 'EUR';
  return cards.reduce((sum, slot) => {
    if (!includeSideboard && slot.isSideboard) {
      return sum;
    }
    const foil = Boolean(slot.isFoil);
    // Never fall back from regular to foil: serialized/SLD foil listings can
    // be thousands while the non-foil printing has no Cardmarket price.
    const unit = foil
      ? priceFor(slot.card, currency, true) ??
        priceFor(slot.card, other, true) ??
        priceFor(slot.card, currency, false) ??
        priceFor(slot.card, other, false) ??
        0
      : priceFor(slot.card, currency, false) ??
        priceFor(slot.card, other, false) ??
        0;
    return sum + unit * slot.quantity;
  }, 0);
}
