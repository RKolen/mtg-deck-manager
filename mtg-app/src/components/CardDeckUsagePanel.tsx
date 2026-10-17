/**
 * Card page panel: which decks use this card (any printing) and how many of
 * the owned copies are left. Maybeboards are listed but do not use copies.
 */

import React from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { fetchCardDeckUsage, type CardDeckUse } from '../services/drupalApi';
import { slugify } from '../utils/slugify';

const BOARD_LABELS: Record<CardDeckUse['board'], string> = {
  main: 'Main',
  side: 'Sideboard',
  maybe: 'Maybeboard',
  commander: 'Commander',
};

interface CardDeckUsagePanelProps {
  cardTitle: string;
}

const CardDeckUsagePanel: React.FC<CardDeckUsagePanelProps> = ({ cardTitle }) => {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['cardDeckUsage', cardTitle],
    queryFn: () => fetchCardDeckUsage(cardTitle),
    enabled: cardTitle !== '',
  });

  const free = data != null ? data.owned - data.inDecks : 0;

  return (
    <section
      aria-label="In decks"
      style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid var(--line)', fontSize: '0.875rem' }}
    >
      <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>In decks</h3>
      {isLoading && <p style={{ margin: 0 }}>Loading...</p>}
      {isError && <p style={{ margin: 0, color: '#c00' }}>Could not load deck usage.</p>}
      {data != null && (
        <>
          <p style={{ margin: '0 0 0.5rem' }}>
            Owned <strong>{data.owned}</strong> · in decks <strong>{data.inDecks}</strong> ·{' '}
            {free >= 0 ? (
              <>
                free <strong>{free}</strong>
              </>
            ) : (
              <span style={{ color: 'var(--warn)' }}>
                short <strong>{-free}</strong>
              </span>
            )}
            <span style={{ opacity: 0.7 }}> (any printing)</span>
          </p>
          {data.decks.length === 0 ? (
            <p style={{ margin: 0, opacity: 0.8 }}>Not in any deck.</p>
          ) : (
            <table className="mono" style={{ borderCollapse: 'collapse', fontSize: 12 }}>
              <tbody>
                {data.decks.map(use => (
                  <tr
                    key={`${use.deckId}-${use.board}-${use.setCode}-${use.foil}`}
                    style={{ opacity: use.board === 'maybe' ? 0.65 : 1 }}
                  >
                    <td style={{ padding: '2px 8px 2px 0' }}>{use.quantity}x</td>
                    <td style={{ padding: '2px 8px 2px 0' }}>
                      <Link href={`/decks/${slugify(use.deckTitle)}`} style={{ color: 'var(--accent)' }}>
                        {use.deckTitle}
                      </Link>
                    </td>
                    <td style={{ padding: '2px 8px 2px 0' }}>{BOARD_LABELS[use.board]}</td>
                    <td style={{ padding: '2px 0' }}>
                      {use.setCode.toUpperCase()}
                      {use.foil ? ' · foil' : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
};

export default CardDeckUsagePanel;
