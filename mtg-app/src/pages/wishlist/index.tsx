/**
 * Wishlist: cards wanted for decks, brews, upgrades and price watches.
 *
 * A wish is done once the collection holds the wanted quantity (any printing
 * or one exact printing). Done wishes are hidden unless "Show done" is on.
 */

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteWishlistItem,
  fetchDecks,
  fetchWishIntents,
  fetchWishlist,
  findCardsByName,
  saveWishlistItem,
  type WishlistItemInput,
} from '../../services/drupalApi';
import WishlistDeckShortfalls from '../../components/WishlistDeckShortfalls';
import { useTheme } from '../../context/ThemeContext';
import { bestPrice, formatPrice, type Currency } from '../../utils/prices';
import { cardImageSrc } from '../../utils/cardImage';
import { cardPrintingsPath, slugify } from '../../utils/slugify';
import type { MtgCard, WishlistItem } from '../../types/drupal';

const fieldStyle: React.CSSProperties = {
  padding: '2px 4px',
  color: '#000',
  background: '#fff',
  border: '1px solid #000',
};

/**
 * Price of one wanted copy: the cheapest priced printing for any-printing
 * wishes (from the server), else the wished printing's price.
 */
function unitPrice(item: WishlistItem, currency: Currency, usdToEur: number | null): number | null {
  const main = currency === 'EUR' ? item.priceEur : item.priceUsd;
  if (main != null) return main;
  return item.card != null ? bestPrice(item.card, currency, item.foil, usdToEur) : null;
}

/** Copies still to get. */
function stillNeeded(item: WishlistItem): number {
  return Math.max(0, item.quantity - item.owned);
}

/** Plain-text list grouped by intent, for mailing or printing. */
function exportText(items: WishlistItem[], currency: Currency, usdToEur: number | null): string {
  const groups = new Map<string, WishlistItem[]>();
  for (const item of items) {
    const key = item.intent?.name ?? 'No intent';
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  const lines: string[] = [
    'MTG WANT LIST',
    `Exported ${new Date().toISOString().slice(0, 10)}. Prices: cheapest printing (${currency}).`,
    'Format: qty x card - price each - details',
  ];
  let total = 0;
  for (const [intent, group] of groups) {
    lines.push('', intent.toUpperCase());
    for (const item of group) {
      const need = stillNeeded(item);
      if (need === 0) continue;
      const price = unitPrice(item, currency, usdToEur);
      total += (price ?? 0) * need;
      const details = [
        item.anyPrinting ? null : `${item.card?.field_set_name ?? ''} #${item.card?.field_collector_number ?? ''}`,
        item.foil ? 'foil' : null,
        item.minCondition ? `${item.minCondition} or better` : null,
        item.deck?.title ?? null,
        item.owned > 0 ? `have ${item.owned} of ${item.quantity}` : null,
        item.notes,
      ].filter(Boolean);
      lines.push(
        `${need}x ${item.card?.title ?? '?'} - ${formatPrice(price, currency)}${details.length ? ` - ${details.join(', ')}` : ''}`,
      );
    }
  }
  lines.push('', `TOTAL: ${formatPrice(total, currency)}`);
  return `${lines.join('\n')}\n`;
}

function download(name: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

/** Small image preview of a wished card; closes on Escape or outside click. */
const WishCardPreview: React.FC<{ item: WishlistItem; currency: Currency; onClose: () => void }> = ({
  item,
  currency,
  onClose,
}) => {
  const { usdToEur } = useTheme();
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const card = item.card;
  if (card == null) return null;
  const printing = [card.field_set_code?.toUpperCase(), card.field_collector_number ? `#${card.field_collector_number}` : null]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={card.title}
      onClick={e => {
        if (e.target === e.currentTarget) onClose();
      }}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: 16,
      }}
    >
      <div
        style={{
          background: 'var(--bg)',
          color: 'var(--ink)',
          border: '1px solid var(--line)',
          borderRadius: 8,
          padding: 12,
          width: 'min(272px, 100%)',
          fontSize: 12,
        }}
      >
        <img
          src={cardImageSrc(card)}
          alt={card.title}
          style={{ width: '100%', borderRadius: 10, display: 'block' }}
        />
        <p style={{ margin: '8px 0 2px', fontWeight: 700 }}>{card.title}</p>
        <p style={{ margin: 0, opacity: 0.8 }}>
          {item.anyPrinting ? `Any printing (shown: ${printing})` : printing}
          {item.foil ? ' · foil' : ''}
          {' · '}
          {formatPrice(unitPrice(item, currency, usdToEur), currency)}
        </p>
        <p style={{ margin: '2px 0 0', opacity: 0.8 }}>
          Have {item.owned} of {item.quantity}
          {item.deck ? ` · ${item.deck.title}` : ''}
        </p>
        <div style={{ display: 'flex', gap: 10, marginTop: 8, alignItems: 'center' }}>
          <Link href={cardPrintingsPath(card.title, { printing: card.id })} style={{ color: 'var(--accent)' }}>
            All printings
          </Link>
          <button type="button" onClick={onClose} style={{ marginLeft: 'auto' }} autoFocus>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

const WishlistPage: React.FC = () => {
  const qc = useQueryClient();
  const { currency, usdToEur } = useTheme();
  const [deckId, setDeckId] = useState('');
  const [intentId, setIntentId] = useState('');
  const [showDone, setShowDone] = useState(false);
  const [addName, setAddName] = useState('');
  const [addQty, setAddQty] = useState(1);
  const [addIntent, setAddIntent] = useState('');
  /** Deck for new wishes; null follows the deck filter. */
  const [addDeck, setAddDeck] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<MtgCard[]>([]);
  const [addError, setAddError] = useState<string | null>(null);
  const [preview, setPreview] = useState<WishlistItem | null>(null);

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['wishlist', deckId, intentId, showDone],
    queryFn: () => fetchWishlist({ deckId, intentId, includeDone: showDone }),
  });
  const { data: intents = [] } = useQuery({
    queryKey: ['wishIntents'],
    queryFn: fetchWishIntents,
    staleTime: 10 * 60_000,
  });
  const { data: decks = [] } = useQuery({ queryKey: ['decks'], queryFn: fetchDecks });

  // A new deck wish can put the card on that deck's maybeboard.
  const refresh = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ['wishlist'] }),
      qc.invalidateQueries({ queryKey: ['deckCards'] }),
      qc.invalidateQueries({ queryKey: ['deckShortfalls'] }),
    ]);
  const save = useMutation({
    mutationFn: (input: WishlistItemInput) => saveWishlistItem(input),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: deleteWishlistItem, onSuccess: refresh });

  function update(item: WishlistItem, changes: Partial<WishlistItemInput>): void {
    if (item.card == null) return;
    save.mutate({ id: item.id, cardId: item.card.id, quantity: item.quantity, ...changes });
  }

  async function addByName(card?: MtgCard): Promise<void> {
    setAddError(null);
    let pick = card;
    if (pick == null) {
      const name = addName.trim();
      if (name === '') return;
      const exact = await findCardsByName(name);
      if (exact.length === 0) {
        const fuzzy = await findCardsByName(name, { contains: true });
        const names = new Map(fuzzy.map(c => [c.attributes.title, c]));
        setCandidates([...names.values()].slice(0, 8));
        if (names.size === 0) setAddError(`No card found for "${name}".`);
        return;
      }
      pick = exact[0];
    }
    await save.mutateAsync({
      cardId: pick.id,
      quantity: addQty,
      anyPrinting: true,
      intentId: addIntent,
      deckId: addDeck ?? deckId,
    });
    setAddName('');
    setAddQty(1);
    setCandidates([]);
  }

  const { openCount, copies, cost, unpriced } = useMemo(() => {
    let count = 0;
    let copyCount = 0;
    let sum = 0;
    let missing = 0;
    for (const item of items) {
      const need = stillNeeded(item);
      if (need > 0) {
        const price = unitPrice(item, currency, usdToEur);
        count += 1;
        copyCount += need;
        sum += (price ?? 0) * need;
        if (price == null) missing += 1;
      }
    }
    return { openCount: count, copies: copyCount, cost: sum, unpriced: missing };
  }, [items, currency, usdToEur]);

  return (
    <main
      style={{
        padding: '1rem 1.5rem',
        color: 'var(--ink)',
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) 300px',
        gap: '1.5rem',
        alignItems: 'start',
      }}
    >
      <div style={{ minWidth: 0 }}>
      <h1 style={{ marginTop: 0 }}>Wishlist</h1>
      <div
        aria-label="Wishlist totals"
        style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', alignItems: 'baseline', margin: '0 0 0.75rem' }}
      >
        <div>
          <div className="mono uc dim" style={{ fontSize: 10, letterSpacing: '0.08em' }}>
            Total to complete{deckId !== '' || intentId !== '' ? ' (filtered)' : ''}
          </div>
          <div style={{ fontSize: 28, fontWeight: 700, lineHeight: 1.1 }}>{formatPrice(cost, currency)}</div>
        </div>
        <div>
          <div className="mono uc dim" style={{ fontSize: 10, letterSpacing: '0.08em' }}>Copies to get</div>
          <div style={{ fontSize: 20, fontWeight: 600 }}>{copies}</div>
        </div>
        <div>
          <div className="mono uc dim" style={{ fontSize: 10, letterSpacing: '0.08em' }}>Open wishes</div>
          <div style={{ fontSize: 20, fontWeight: 600 }}>{openCount}</div>
        </div>
        {unpriced > 0 && (
          <div style={{ color: 'var(--warn)', fontSize: 12 }}>
            {unpriced} without a price (not in the total)
          </div>
        )}
      </div>
      <p style={{ marginTop: 0, fontSize: 12, opacity: 0.8 }}>
        Prices use the cheapest printing for any-printing wishes. Add cards here or from a card page.
      </p>

      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center', marginBottom: '1rem' }}>
        <label>
          Deck{' '}
          <select value={deckId} onChange={e => setDeckId(e.target.value)} style={fieldStyle}>
            <option value="">All</option>
            {decks.map(d => (
              <option key={d.id} value={d.id}>
                {d.attributes.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Intent{' '}
          <select value={intentId} onChange={e => setIntentId(e.target.value)} style={fieldStyle}>
            <option value="">All</option>
            {intents.map(i => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={showDone} onChange={e => setShowDone(e.target.checked)} /> Show done
        </label>
        <button type="button" onClick={() => download('want-list.txt', exportText(items, currency, usdToEur))} disabled={items.length === 0}>
          Export .txt
        </button>
      </div>

      <form
        onSubmit={e => {
          e.preventDefault();
          void addByName();
        }}
        style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center', marginBottom: '1rem' }}
      >
        <label htmlFor="wish-add-name">Add card</label>
        <input
          id="wish-add-name"
          type="text"
          value={addName}
          onChange={e => setAddName(e.target.value)}
          placeholder="Card name"
          style={{ ...fieldStyle, width: 220 }}
        />
        <input
          type="number"
          min={1}
          value={addQty}
          onChange={e => setAddQty(Math.max(1, Number.parseInt(e.target.value, 10) || 1))}
          aria-label="Quantity"
          style={{ ...fieldStyle, width: 56 }}
        />
        <select value={addIntent} onChange={e => setAddIntent(e.target.value)} aria-label="Intent" style={fieldStyle}>
          <option value="">No intent</option>
          {intents.map(i => (
            <option key={i.id} value={i.id}>
              {i.name}
            </option>
          ))}
        </select>
        <select
          value={addDeck ?? deckId}
          onChange={e => setAddDeck(e.target.value)}
          aria-label="Deck"
          title="A wish for a deck also goes on that deck's maybeboard. The deck cannot be changed later."
          style={{ ...fieldStyle, maxWidth: 180 }}
        >
          <option value="">No deck</option>
          {decks.map(d => (
            <option key={d.id} value={d.id}>
              {d.attributes.title}
            </option>
          ))}
        </select>
        <button type="submit" disabled={save.isPending}>
          Add
        </button>
        {candidates.length > 0 && (
          <span>
            Did you mean:{' '}
            {candidates.map(c => (
              <button key={c.id} type="button" onClick={() => void addByName(c)} style={{ marginRight: 4 }}>
                {c.attributes.title}
              </button>
            ))}
          </span>
        )}
        {addError != null && (
          <span role="alert" style={{ color: '#c00' }}>
            {addError}
          </span>
        )}
      </form>

      {isLoading && <p>Loading wishlist...</p>}
      {!isLoading && items.length === 0 && <p>No wishes match these filters.</p>}

      {items.length > 0 && (
        <table className="mono" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--line)' }}>
              <th style={{ padding: 4 }}>Card</th>
              <th style={{ padding: 4 }}>Printing</th>
              <th style={{ padding: 4 }}>Foil</th>
              <th style={{ padding: 4 }}>Want</th>
              <th style={{ padding: 4 }}>Have</th>
              <th style={{ padding: 4 }}>Intent</th>
              <th style={{ padding: 4 }}>Deck</th>
              <th style={{ padding: 4 }}>Min. cond.</th>
              <th style={{ padding: 4, textAlign: 'right' }}>Each</th>
              <th style={{ padding: 4, textAlign: 'right' }}>To complete</th>
              <th style={{ padding: 4 }}>Notes</th>
              <th style={{ padding: 4 }} aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {items.map(item => {
              const price = unitPrice(item, currency, usdToEur);
              const need = stillNeeded(item);
              const card = item.card;
              return (
                <tr key={item.id} style={{ borderBottom: '1px solid var(--line)', opacity: item.done ? 0.6 : 1 }}>
                  <td style={{ padding: 4 }}>
                    {card != null ? (
                      <button
                        type="button"
                        onClick={() => setPreview(item)}
                        title="Show card"
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          color: 'var(--ink)',
                          textDecoration: 'underline',
                          cursor: 'pointer',
                          font: 'inherit',
                          textAlign: 'left',
                        }}
                      >
                        {card.title}
                      </button>
                    ) : (
                      '?'
                    )}
                    {item.foil && (
                      <span
                        className="mono"
                        style={{
                          marginLeft: 6,
                          padding: '0 4px',
                          fontSize: 9,
                          letterSpacing: '0.08em',
                          border: '1px solid var(--accent)',
                          color: 'var(--accent)',
                          borderRadius: 3,
                          verticalAlign: 'middle',
                        }}
                      >
                        FOIL
                      </span>
                    )}
                  </td>
                  <td style={{ padding: 4 }}>
                    <label>
                      <input
                        type="checkbox"
                        checked={item.anyPrinting}
                        onChange={e => update(item, { anyPrinting: e.target.checked })}
                      />{' '}
                      {item.anyPrinting ? 'Any' : `${card?.field_set_code?.toUpperCase() ?? ''} #${card?.field_collector_number ?? ''}`}
                    </label>
                  </td>
                  <td style={{ padding: 4, textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={item.foil}
                      onChange={e => update(item, { foil: e.target.checked })}
                      aria-label={`Foil ${card?.title ?? ''}`}
                      title="Only foil copies count toward this wish"
                    />
                  </td>
                  <td style={{ padding: 4, whiteSpace: 'nowrap' }}>
                    <button type="button" onClick={() => update(item, { quantity: item.quantity - 1 })} disabled={item.quantity <= 1} style={{ width: 22, padding: 0 }}>
                      -
                    </button>{' '}
                    {item.quantity}{' '}
                    <button type="button" onClick={() => update(item, { quantity: item.quantity + 1 })} style={{ width: 22, padding: 0 }}>
                      +
                    </button>
                  </td>
                  <td style={{ padding: 4 }}>{item.done ? `${item.owned} (done)` : item.owned}</td>
                  <td style={{ padding: 4 }}>
                    <select
                      value={item.intent?.id ?? ''}
                      onChange={e => update(item, { intentId: e.target.value })}
                      aria-label="Intent"
                      style={fieldStyle}
                    >
                      <option value="">None</option>
                      {intents.map(i => (
                        <option key={i.id} value={i.id}>
                          {i.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td style={{ padding: 4, whiteSpace: 'nowrap' }}>
                    {item.deck != null ? (
                      <Link
                        href={`/decks/${slugify(item.deck.title)}`}
                        title={`Open ${item.deck.title}`}
                        style={{ color: 'var(--accent)' }}
                      >
                        {item.deck.title}
                      </Link>
                    ) : (
                      <span style={{ opacity: 0.6 }}>-</span>
                    )}
                  </td>
                  <td style={{ padding: 4 }}>{item.minCondition ?? 'Any'}</td>
                  <td style={{ padding: 4, textAlign: 'right' }}>{formatPrice(price, currency)}</td>
                  <td style={{ padding: 4, textAlign: 'right' }}>{need > 0 ? formatPrice((price ?? 0) * need, currency) : '-'}</td>
                  <td style={{ padding: 4 }}>
                    <input
                      key={`${item.id}-${item.notes ?? ''}`}
                      type="text"
                      defaultValue={item.notes ?? ''}
                      onBlur={e => {
                        if (e.target.value !== (item.notes ?? '')) update(item, { notes: e.target.value });
                      }}
                      aria-label="Notes"
                      style={{ ...fieldStyle, width: '100%' }}
                    />
                  </td>
                  <td style={{ padding: 4 }}>
                    <button type="button" onClick={() => remove.mutate(item.id)}>
                      Remove
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      </div>

      <div style={{ position: 'sticky', top: 0 }}>
        <WishlistDeckShortfalls
          currency={currency}
          usdToEur={usdToEur}
          activeDeckId={deckId}
          onSelectDeck={setDeckId}
        />
      </div>

      {preview != null && (
        <WishCardPreview item={preview} currency={currency} onClose={() => setPreview(null)} />
      )}
    </main>
  );
};

export default WishlistPage;
