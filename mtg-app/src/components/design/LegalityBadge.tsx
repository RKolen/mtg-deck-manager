import React from 'react';
import type { DeckLegality } from '../../utils/deckAnalysis';

/**
 * Compact INVALID marker for decks that fail constructed legality.
 */
export function LegalityBadge({
  legality,
}: {
  legality: DeckLegality | null;
}) {
  if (legality == null || legality.ok) {
    return null;
  }
  const summary = legality.issues.map(issue => issue.message).join('\n');
  return (
    <span
      title={summary}
      className="mono"
      style={{
        display: 'inline-block',
        marginLeft: 8,
        padding: '1px 6px',
        borderRadius: 2,
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: '0.08em',
        background: 'var(--neg)',
        color: 'var(--bg)',
        verticalAlign: 'middle',
        whiteSpace: 'nowrap',
      }}
    >
      INVALID
    </span>
  );
}
