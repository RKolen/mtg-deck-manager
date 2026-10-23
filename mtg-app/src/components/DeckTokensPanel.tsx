/**
 * Deck page panel: the tokens, emblems and game pieces the deck makes.
 *
 * Built from Scryfall's card-to-token links, so no oracle text parsing.
 * Each token appears once however many cards make it; printings merge only
 * when name, stats and abilities match, so a 0/0 and a 1/1 Construct stay
 * apart. Maybeboard cards are not counted.
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchDeckTokens, type DeckToken } from '../services/drupalApi';

const KIND_LABELS: Record<DeckToken['kind'], string> = {
  token: 'Tokens',
  emblem: 'Emblems',
  game: 'Game pieces',
};

const KIND_ORDER: DeckToken['kind'][] = ['token', 'emblem', 'game'];

interface DeckTokensPanelProps {
  deckId: string;
}

/** "Token Artifact Creature — Thopter" becomes "Artifact Creature — Thopter". */
function shortType(typeLine: string): string {
  return typeLine.replace(/^Token\s+/, '');
}

function TokenEntry({ token }: { token: DeckToken }): React.ReactElement {
  const stats = token.power != null && token.toughness != null ? `${token.power}/${token.toughness}` : null;
  const owned = token.owned > 0;
  return (
    <div
      style={{
        display: 'flex',
        gap: 10,
        padding: 8,
        border: `1px solid ${owned ? 'var(--line)' : 'var(--warn)'}`,
        borderRadius: 4,
        background: 'var(--bg-2)',
        color: 'var(--ink)',
        fontSize: 13,
      }}
    >
      {token.card?.imageUri ? (
        <img
          src={token.card.imageUri}
          alt={token.name}
          title={token.card.setCode ? `${token.card.setCode.toUpperCase()} #${token.card.collectorNumber ?? ''}` : undefined}
          style={{ width: 64, borderRadius: 4, alignSelf: 'flex-start', flexShrink: 0 }}
        />
      ) : (
        <div style={{ width: 64, flexShrink: 0 }} />
      )}
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 700 }}>
          {token.name}
          {stats != null && <span style={{ marginLeft: 6, fontWeight: 'normal' }}>{stats}</span>}
        </div>
        <div style={{ opacity: 0.8, fontSize: 12 }}>{shortType(token.typeLine)}</div>
        {token.oracleText && (
          <div style={{ marginTop: 4, fontSize: 12, whiteSpace: 'pre-line' }}>{token.oracleText}</div>
        )}
        <div style={{ marginTop: 4, fontSize: 12, opacity: 0.85 }}>Made by: {token.madeBy.join(', ')}</div>
        <div style={{ marginTop: 4, fontSize: 12, color: owned ? 'var(--pos)' : 'var(--warn)' }}>
          {owned ? `Owned ${token.owned}` : 'Missing'}
        </div>
      </div>
    </div>
  );
}

const DeckTokensPanel: React.FC<DeckTokensPanelProps> = ({ deckId }) => {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['deckTokens', deckId],
    queryFn: () => fetchDeckTokens(deckId),
    enabled: deckId !== '',
  });

  const tokens = data ?? [];
  const missing = tokens.filter(t => t.owned < 1).length;

  return (
    <section style={{ marginTop: '1.5rem' }}>
      <h3
        style={{
          margin: '0 0 0.4rem',
          borderBottom: '2px solid var(--line)',
          paddingBottom: '0.25rem',
          color: 'var(--ink)',
        }}
      >
        Tokens &amp; emblems
        <span style={{ marginLeft: 8, color: 'var(--ink)', fontWeight: 'normal', fontSize: '0.9rem' }}>
          ({tokens.length})
        </span>
        {tokens.length > 0 && (
          <span style={{ marginLeft: 12, fontWeight: 'normal', fontSize: '0.8rem', opacity: 0.75 }}>
            {missing === 0 ? 'all owned' : `${missing} missing`}
          </span>
        )}
      </h3>
      {isLoading && <p style={{ color: 'var(--ink)' }}>Loading...</p>}
      {isError && <p style={{ color: 'var(--warn)' }}>Could not load the token list.</p>}
      {data != null && tokens.length === 0 && (
        <p style={{ color: 'var(--ink)', opacity: 0.75 }}>This deck makes no tokens or emblems.</p>
      )}
      {KIND_ORDER.map(kind => {
        const group = tokens.filter(t => t.kind === kind);
        if (group.length === 0) {
          return null;
        }
        return (
          <div key={kind} style={{ marginBottom: '0.75rem' }}>
            <h4 style={{ margin: '0.5rem 0 0.4rem', color: 'var(--ink)' }}>{KIND_LABELS[kind]}</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.5rem' }}>
              {group.map(token => (
                <TokenEntry key={`${token.name}|${token.typeLine}|${token.power}|${token.toughness}|${token.oracleText}`} token={token} />
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
};

export default DeckTokensPanel;
