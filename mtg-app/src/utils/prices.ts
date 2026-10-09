import type { CollectionCardAttributes, MtgCardAttributes } from '../types/drupal';

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

type PricedCard = Pick<
  MtgCardAttributes,
  'field_price_usd' | 'field_price_usd_foil' | 'field_price_eur' | 'field_price_eur_foil'
>;

/**
 * Price of one copy with fallbacks, for values, totals and sorting.
 *
 * Order: the asked finish in the asked currency, the other finish in that
 * currency, then the same two in the other currency converted at usdToEur
 * (euros per dollar). A foil-only or regular-only printing gets a price
 * instead of none. Without a rate the other currency is never used, so a USD
 * amount is never passed off as EUR.
 */
export function bestPrice(
  card: PricedCard,
  currency: Currency,
  foil = false,
  usdToEur: number | null = null,
): number | null {
  const own = priceFor(card, currency, foil) ?? priceFor(card, currency, !foil);
  if (own != null || usdToEur == null || usdToEur <= 0) {
    return own;
  }
  const other: Currency = currency === 'EUR' ? 'USD' : 'EUR';
  const raw = priceFor(card, other, foil) ?? priceFor(card, other, !foil);
  if (raw == null) {
    return null;
  }
  return currency === 'EUR' ? raw * usdToEur : raw / usdToEur;
}

/** Unit price for a deck slot; 0 when the card has no price at all. */
export function slotUnitPrice(
  card: PricedCard,
  currency: Currency,
  foil = false,
  usdToEur: number | null = null,
): number {
  return bestPrice(card, currency, foil, usdToEur) ?? 0;
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
  usdToEur: number | null = null,
): number {
  return cards.reduce((sum, slot) => {
    if (!includeSideboard && slot.isSideboard) {
      return sum;
    }
    return sum + slotUnitPrice(slot.card, currency, Boolean(slot.isFoil), usdToEur) * slot.quantity;
  }, 0);
}

/**
 * Value of a collection row's trade copies.
 *
 * Trade copies are counted as regular copies first; only copies beyond the
 * regular ones are valued at the foil price. Both use bestPrice fallbacks.
 */
export function tradeValue(
  cc: CollectionCardAttributes,
  currency: Currency,
  usdToEur: number | null = null,
): number {
  const owned = cc.field_quantity_owned ?? 0;
  const foil = cc.field_quantity_foil ?? 0;
  const trade = Math.min(cc.field_quantity_trade ?? 0, owned + foil);
  const regularCopies = Math.min(trade, owned);
  const foilCopies = trade - regularCopies;
  const card: PricedCard = {
    field_price_eur: cc.field_price_eur ?? null,
    field_price_eur_foil: cc.field_price_eur_foil ?? null,
    field_price_usd: cc.field_price_usd ?? null,
    field_price_usd_foil: cc.field_price_usd_foil ?? null,
  };
  return (
    regularCopies * (bestPrice(card, currency, false, usdToEur) ?? 0) +
    foilCopies * (bestPrice(card, currency, true, usdToEur) ?? 0)
  );
}
