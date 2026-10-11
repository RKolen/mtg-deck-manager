import React, { useMemo } from 'react';
import Link from 'next/link';
import { collectionPrintingId } from '../services/drupalApi';
import type { CollectionCard } from '../types/drupal';
import { cardPrintingsPath } from '../utils/slugify';
import { bestPrice, formatPrice, type Currency } from '../utils/prices';

interface TopCollectionCardsProps {
  rows: CollectionCard[];
  currency: Currency;
  usdToEur: number | null;
  /** How many cards to list. */
  limit?: number;
}

interface TopEntry {
  key: string;
  title: string;
  setCode: string;
  printingId: string | null;
  foil: boolean;
  price: number;
  copies: number;
}

/**
 * The most valuable single cards in the collection: one entry per printing
 * and finish, ranked by the price of one copy.
 */
const TopCollectionCards: React.FC<TopCollectionCardsProps> = ({ rows, currency, usdToEur, limit = 10 }) => {
  const top = useMemo(() => {
    const entries: TopEntry[] = [];
    for (const cc of rows) {
      const a = cc.attributes;
      const finishes: [boolean, number][] = [
        [false, a.field_quantity_owned ?? 0],
        [true, a.field_quantity_foil ?? 0],
      ];
      for (const [foil, copies] of finishes) {
        if (copies <= 0) {
          continue;
        }
        const price = bestPrice(
          {
            field_price_eur: a.field_price_eur ?? null,
            field_price_eur_foil: a.field_price_eur_foil ?? null,
            field_price_usd: a.field_price_usd ?? null,
            field_price_usd_foil: a.field_price_usd_foil ?? null,
          },
          currency,
          foil,
          usdToEur,
        );
        if (price == null) {
          continue;
        }
        entries.push({
          key: `${cc.id}-${foil ? 'f' : 'n'}`,
          title: a.field_card_title ?? '',
          setCode: (a.field_set_code ?? '').toUpperCase(),
          printingId: collectionPrintingId(cc),
          foil,
          price,
          copies,
        });
      }
    }
    return entries.sort((x, y) => y.price - x.price).slice(0, limit);
  }, [rows, currency, usdToEur, limit]);

  if (top.length === 0) {
    return null;
  }

  return (
    <aside className="summary-card" style={{ padding: '1rem', minWidth: 160, marginTop: '1rem' }}>
      <h3 style={{ margin: '0 0 0.75rem', color: 'var(--ink)' }}>Most valuable</h3>
      <ol style={{ margin: 0, paddingLeft: '1.25rem', color: 'var(--ink)', fontSize: '0.85rem' }}>
        {top.map(e => (
          <li key={e.key} style={{ marginBottom: '0.4rem' }}>
            <Link
              href={cardPrintingsPath(e.title, { printing: e.printingId ?? undefined, foil: e.foil || undefined })}
              style={{ color: 'var(--ink)' }}
            >
              {e.title}
            </Link>
            <div className="mono dim" style={{ fontSize: 11 }}>
              {e.setCode}
              {e.foil ? ' foil' : ''}
              {e.copies > 1 ? ` x${e.copies}` : ''}
              {' '}
              <span className="tnum" style={{ fontWeight: 700, color: 'var(--ink)' }}>
                {formatPrice(e.price, currency)}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </aside>
  );
};

export default TopCollectionCards;
