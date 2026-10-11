import React, { useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchDeckShortfalls, saveWishlistItem, type DeckShortfall } from '../services/drupalApi';
import { bestPrice, formatPrice, type Currency } from '../utils/prices';
import { cardPrintingsPath, slugify } from '../utils/slugify';

interface WishlistDeckShortfallsProps {
  currency: Currency;
  usdToEur: number | null;
  /** Deck currently used as the wishlist filter ('' for all). */
  activeDeckId: string;
  /** Filters the wishlist to a deck. */
  onSelectDeck: (deckId: string) => void;
}

function missingCopies(deck: DeckShortfall): number {
  return deck.cards.reduce((s, c) => s + c.needed - c.owned, 0);
}

/**
 * Decks with main deck or sideboard cards that are not owned (any printing).
 * Each deck can be expanded, used as the wishlist filter, or have all its
 * unwished missing cards added to the wishlist.
 */
const WishlistDeckShortfalls: React.FC<WishlistDeckShortfallsProps> = ({
  currency,
  usdToEur,
  activeDeckId,
  onSelectDeck,
}) => {
  const qc = useQueryClient();
  const [open, setOpen] = useState<string | null>(null);
  const { data: decks = [], isLoading } = useQuery({
    queryKey: ['deckShortfalls'],
    queryFn: fetchDeckShortfalls,
    staleTime: 60_000,
  });

  const wishMissing = useMutation({
    mutationFn: async (deck: DeckShortfall) => {
      // Wish quantities are total copies wanted; owned copies count toward them.
      // Only cards without any wish for this deck, so no duplicate wishes.
      for (const c of deck.cards.filter(x => x.wished === 0)) {
        await saveWishlistItem({ cardId: c.card.id, quantity: c.needed, anyPrinting: true, deckId: deck.deckId });
      }
    },
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['wishlist'] }),
        qc.invalidateQueries({ queryKey: ['deckShortfalls'] }),
      ]);
    },
  });

  return (
    <aside className="summary-card" style={{ padding: '1rem', color: 'var(--ink)' }}>
      <h3 style={{ margin: '0 0 0.25rem' }}>Decks missing cards</h3>
      <p className="dim" style={{ margin: '0 0 0.75rem', fontSize: 12 }}>
        Main deck and sideboard cards you own no copy of (any printing).
      </p>
      {isLoading && <p style={{ fontSize: 12 }}>Loading...</p>}
      {!isLoading && decks.length === 0 && <p style={{ fontSize: 12 }}>Every deck is complete.</p>}
      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {decks.map(deck => {
          const copies = missingCopies(deck);
          // Cheapest printing, like the wishlist; the deck's printing only as
          // a fallback.
          const cost = deck.cards.reduce((s, c) => {
            const cheapest = currency === 'EUR' ? c.priceEur : c.priceUsd;
            const price = cheapest ?? bestPrice(c.card.attributes, currency, false, usdToEur) ?? 0;
            return s + price * (c.needed - c.owned);
          }, 0);
          const unwished = deck.cards.filter(c => c.wished === 0).length;
          const expanded = open === deck.deckId;
          const active = activeDeckId === deck.deckId;
          return (
            <li key={deck.deckId} style={{ borderTop: '1px solid var(--line)', padding: '0.5rem 0' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <button
                  type="button"
                  onClick={() => setOpen(expanded ? null : deck.deckId)}
                  aria-expanded={expanded}
                  style={{ background: 'none', border: 0, padding: 0, color: 'var(--ink)', cursor: 'pointer', textAlign: 'left', flex: 1 }}
                >
                  <span className="mono dim">{expanded ? '-' : '+'}</span>{' '}
                  <strong>{deck.deckTitle}</strong>
                </button>
                <span className="mono tnum" style={{ fontSize: 12 }}>{formatPrice(cost, currency)}</span>
              </div>
              <div className="mono dim" style={{ fontSize: 11, marginLeft: 14 }}>
                {deck.format !== '' ? `${deck.format}, ` : ''}
                {copies} cop{copies === 1 ? 'y' : 'ies'} of {deck.cards.length} card{deck.cards.length === 1 ? '' : 's'}
                {unwished === 0 ? ', all wished' : `, ${unwished} not wished`}
              </div>
              <div style={{ display: 'flex', gap: 8, marginLeft: 14, marginTop: 4, fontSize: 12 }}>
                <button type="button" onClick={() => onSelectDeck(active ? '' : deck.deckId)}>
                  {active ? 'Show all wishes' : 'Show wishes'}
                </button>
                {unwished > 0 && (
                  <button
                    type="button"
                    disabled={wishMissing.isPending}
                    onClick={() => wishMissing.mutate(deck)}
                  >
                    Wish missing
                  </button>
                )}
                <Link href={`/decks/${slugify(deck.deckTitle)}`} style={{ color: 'var(--accent)', alignSelf: 'center' }}>
                  Open deck
                </Link>
              </div>
              {expanded && (
                <ul style={{ margin: '0.4rem 0 0 14px', padding: 0, listStyle: 'none', fontSize: 12 }}>
                  {deck.cards.map(c => (
                    <li key={c.card.id} style={{ display: 'flex', gap: 6, padding: '2px 0' }}>
                      <span className="mono tnum">{c.needed - c.owned}x</span>
                      <Link href={cardPrintingsPath(c.card.attributes.title, { printing: c.card.id })} style={{ color: 'var(--ink)', flex: 1 }}>
                        {c.card.attributes.title}
                      </Link>
                      {c.owned > 0 && <span className="dim">has {c.owned}</span>}
                      {c.wished > 0 && (
                        <span className="dim">{c.wished >= c.needed ? 'wished' : `wished ${c.wished}/${c.needed}`}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
      {wishMissing.isError && (
        <p style={{ color: 'var(--neg)', fontSize: 12 }}>
          {wishMissing.error instanceof Error ? wishMissing.error.message : 'Adding wishes failed.'}
        </p>
      )}
    </aside>
  );
};

export default WishlistDeckShortfalls;
