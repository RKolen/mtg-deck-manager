import React from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { fetchPriceMovers, type PriceMover } from '../services/drupalApi';
import { cardPrintingsPath } from '../utils/slugify';
import { formatPrice, type Currency } from '../utils/prices';

interface PriceTickerProps {
  currency: Currency;
}

function TickerItem({ mover, currency, copy = false }: { mover: PriceMover; currency: Currency; copy?: boolean }) {
  const up = mover.changePct > 0;
  const a = mover.card.attributes;
  return (
    <Link
      href={cardPrintingsPath(a.title, { printing: mover.card.id })}
      title={`${a.title} (${a.field_set_name}): ${formatPrice(mover.previous, currency)} to ${formatPrice(mover.current, currency)}`}
      className="mono"
      tabIndex={copy ? -1 : undefined}
      style={{
        display: 'inline-flex',
        alignItems: 'baseline',
        gap: 6,
        padding: '0 1.5rem',
        borderRight: '1px solid var(--line)',
        color: 'var(--ink)',
        textDecoration: 'none',
        fontSize: 12,
      }}
    >
      <span style={{ fontWeight: 700 }}>{a.title}</span>
      <span className="dim">{a.field_set_code.toUpperCase()}</span>
      <span className="tnum">{formatPrice(mover.current, currency)}</span>
      <span className="tnum" style={{ color: up ? 'var(--pos)' : 'var(--neg)', fontWeight: 700 }}>
        {up ? '▲' : '▼'} {up ? '+' : ''}{mover.changePct.toFixed(1)}%
      </span>
    </Link>
  );
}

/**
 * Stock-market style strip with the cards whose price moved most (in
 * percent) since the previous price import. Any card, owned or not.
 * Pauses on hover; static and scrollable with reduced motion.
 */
const PriceTicker: React.FC<PriceTickerProps> = ({ currency }) => {
  const { data } = useQuery({
    queryKey: ['priceMovers', currency],
    queryFn: () => fetchPriceMovers(currency, 10, 1),
    staleTime: 30 * 60 * 1000,
  });

  if (data == null) {
    return null;
  }

  const since = data.since != null
    ? new Date(data.since * 1000).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
    : null;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        borderTop: '1px solid var(--line)',
        background: 'var(--bg-2)',
        minHeight: 32,
      }}
    >
      <span
        className="mono uc"
        style={{
          flex: '0 0 auto',
          padding: '0 0.75rem',
          fontSize: 10,
          letterSpacing: '0.08em',
          color: 'var(--ink)',
          borderRight: '1px solid var(--line)',
        }}
        title="Biggest price changes since the previous price import (cards of 1 or more)"
      >
        Movers{since != null ? ` since ${since}` : ''}
      </span>
      {data.movers.length === 0 ? (
        <span className="mono dim" style={{ padding: '0 0.75rem', fontSize: 12 }}>
          No price changes yet. They appear after the next price import.
        </span>
      ) : (
        <div className="price-ticker" style={{ overflow: 'hidden', flex: 1 }}>
          <div className="price-ticker-track">
            {data.movers.map(m => <TickerItem key={`a-${m.card.id}`} mover={m} currency={currency} />)}
            {/* Second copy for a seamless loop; hidden from screen readers. */}
            <span aria-hidden="true" style={{ display: 'inline-flex' }}>
              {data.movers.map(m => <TickerItem key={`b-${m.card.id}`} mover={m} currency={currency} copy />)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default PriceTicker;
