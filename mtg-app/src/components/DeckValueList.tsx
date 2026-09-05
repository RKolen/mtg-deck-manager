/**
 * Deck cards ranked by line value (quantity * finish-aware unit price).
 */

import React, { useMemo } from 'react';
import type { DeckCardWithCard, DeckCommander } from '../types/drupal';
import { COMMANDER_SLOT } from '../utils/slugify';
import {
  formatPrice,
  slotUnitPrice,
  type Currency,
} from '../utils/prices';

export interface DeckValueListProps {
  cards: DeckCardWithCard[];
  currency: Currency;
  commander?: DeckCommander | null;
  commanderFoil?: boolean;
  commanderLabel?: string;
  selectedSlotId: string | null;
  onSelect: (slotId: string) => void;
}

interface ValueRow {
  slotId: string;
  title: string;
  quantity: number;
  line: number;
  zone: 'commander' | 'main' | 'sideboard';
  foil: boolean;
}

function zoneTag(zone: ValueRow['zone'], commanderLabel: string): string | null {
  if (zone === 'commander') {
    return commanderLabel;
  }
  if (zone === 'sideboard') {
    return 'SB';
  }
  return null;
}

const DeckValueList: React.FC<DeckValueListProps> = ({
  cards,
  currency,
  commander,
  commanderFoil = false,
  commanderLabel = 'Commander',
  selectedSlotId,
  onSelect,
}) => {
  const rows = useMemo(() => {
    const items: ValueRow[] = [];
    if (commander != null) {
      const unit = slotUnitPrice(commander, currency, commanderFoil);
      items.push({
        slotId: COMMANDER_SLOT,
        title: commander.title,
        quantity: 1,
        line: unit,
        zone: 'commander',
        foil: commanderFoil,
      });
    }
    for (const slot of cards) {
      const unit = slotUnitPrice(slot.card, currency, slot.isFoil);
      items.push({
        slotId: slot.id,
        title: slot.card.title,
        quantity: slot.quantity,
        line: unit * slot.quantity,
        zone: slot.isSideboard ? 'sideboard' : 'main',
        foil: slot.isFoil,
      });
    }
    items.sort((a, b) => {
      if (a.line !== b.line) {
        return b.line - a.line;
      }
      return a.title.localeCompare(b.title);
    });
    return items;
  }, [cards, commander, commanderFoil, currency]);

  const total = rows.reduce((sum, row) => sum + row.line, 0);
  const priced = rows.filter(row => row.line > 0).length;

  return (
    <section
      style={{
        width: 260,
        flexShrink: 0,
        position: 'sticky',
        top: 16,
        alignSelf: 'flex-start',
        maxHeight: 'calc(100vh - 32px)',
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid var(--line)',
        borderRadius: 4,
        background: 'var(--bg-1)',
        overflow: 'hidden',
      }}
    >
      <header
        style={{
          padding: '0.55rem 0.7rem 0.45rem',
          borderBottom: '1px solid var(--line)',
          background: 'var(--bg-2)',
        }}
      >
        <div
          className="mono uc dim"
          style={{ fontSize: 9, letterSpacing: '0.08em', marginBottom: 4 }}
        >
          By value
        </div>
        <div style={{ fontWeight: 700, fontSize: 15 }}>
          {formatPrice(total > 0 ? total : null, currency)}
        </div>
        <div className="mono dim" style={{ fontSize: 10, marginTop: 2 }}>
          {priced} priced · {rows.length} unique
        </div>
      </header>
      {rows.length === 0 ? (
        <p style={{ margin: 12, fontSize: 13, opacity: 0.7 }}>
          Add cards to see a value ranking.
        </p>
      ) : (
        <ol
          style={{
            listStyle: 'none',
            margin: 0,
            padding: 0,
            overflowY: 'auto',
          }}
        >
          {rows.map((row, index) => {
            const selected = selectedSlotId === row.slotId;
            const tag = zoneTag(row.zone, commanderLabel);
            return (
              <li key={row.slotId}>
                <button
                  type="button"
                  onClick={() => onSelect(row.slotId)}
                  style={{
                    display: 'flex',
                    width: '100%',
                    gap: 8,
                    alignItems: 'baseline',
                    padding: '0.4rem 0.7rem',
                    border: 0,
                    borderBottom: '1px solid var(--line)',
                    background: selected ? 'var(--bg-2)' : 'transparent',
                    outline: selected ? '1px solid var(--accent)' : undefined,
                    outlineOffset: -1,
                    color: 'var(--ink)',
                    textAlign: 'left',
                    cursor: 'pointer',
                    font: 'inherit',
                  }}
                >
                  <span
                    className="mono dim tnum"
                    style={{ width: 18, flexShrink: 0, fontSize: 10 }}
                  >
                    {index + 1}
                  </span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span
                      style={{
                        display: 'block',
                        fontWeight: 600,
                        fontSize: 12,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {row.quantity > 1 ? `${row.quantity} ` : ''}
                      {row.title}
                    </span>
                    {(tag != null || row.foil) && (
                      <span className="mono dim" style={{ fontSize: 9 }}>
                        {[tag, row.foil ? 'foil' : null].filter(Boolean).join(' · ')}
                      </span>
                    )}
                  </span>
                  <span
                    className="tnum"
                    style={{
                      flexShrink: 0,
                      fontSize: 11,
                      opacity: row.line > 0 ? 1 : 0.45,
                    }}
                  >
                    {formatPrice(row.line > 0 ? row.line : null, currency)}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
};

export default DeckValueList;
