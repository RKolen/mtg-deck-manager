import React, { useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteWishlistItem,
  fetchCollectionCardByCardId,
  fetchDecks,
  fetchWishIntents,
  fetchWishlistForCard,
  saveWishlistItem,
} from '../services/drupalApi';
import { WISH_CONDITIONS } from '../types/drupal';

interface WishlistPanelProps {
  /** The printing shown on the page. */
  cardId: string;
  cardTitle: string;
}

const fieldStyle: React.CSSProperties = {
  padding: '2px 4px',
  color: '#000',
  background: '#fff',
  border: '1px solid #000',
};

/**
 * Collection and wishlist status for one printing, with an add-to-wishlist
 * form. Wishes for any printing of the card show here too.
 */
const WishlistPanel: React.FC<WishlistPanelProps> = ({ cardId, cardTitle }) => {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [quantity, setQuantity] = useState(1);
  const [anyPrinting, setAnyPrinting] = useState(true);
  const [foil, setFoil] = useState(false);
  const [intentId, setIntentId] = useState('');
  const [deckId, setDeckId] = useState('');
  const [minCondition, setMinCondition] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);

  const { data: owned } = useQuery({
    queryKey: ['collectionByCard', cardId],
    queryFn: () => fetchCollectionCardByCardId(cardId),
    enabled: cardId !== '',
  });
  const { data: wishes = [] } = useQuery({
    queryKey: ['wishlist', 'card', cardId],
    queryFn: () => fetchWishlistForCard(cardId),
    enabled: cardId !== '',
  });
  const { data: intents = [] } = useQuery({
    queryKey: ['wishIntents'],
    queryFn: fetchWishIntents,
    staleTime: 10 * 60_000,
  });
  const { data: decks = [] } = useQuery({
    queryKey: ['decks'],
    queryFn: fetchDecks,
    enabled: open,
    staleTime: 60_000,
  });

  const save = useMutation({
    mutationFn: () =>
      saveWishlistItem({
        cardId,
        quantity,
        anyPrinting,
        foil,
        intentId,
        deckId,
        minCondition,
        notes,
      }),
    onSuccess: async () => {
      setOpen(false);
      setError(null);
      setNotes('');
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['wishlist'] }),
        qc.invalidateQueries({ queryKey: ['deckCards'] }),
      ]);
    },
    onError: (err: unknown) => setError(err instanceof Error ? err.message : 'Could not save.'),
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteWishlistItem(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wishlist'] }),
  });

  const regular = owned?.attributes.field_quantity_owned ?? 0;
  const foilCopies = owned?.attributes.field_quantity_foil ?? 0;
  const trade = owned?.attributes.field_quantity_trade ?? 0;

  return (
    <section
      aria-label="Collection and wishlist"
      style={{ marginTop: '0.75rem', fontSize: '0.85rem', borderTop: '1px solid var(--line)', paddingTop: '0.5rem' }}
    >
      <p style={{ margin: '0 0 0.4rem' }}>
        <strong>This printing in your collection:</strong>{' '}
        {regular + foilCopies === 0
          ? 'none'
          : `${regular} regular, ${foilCopies} foil${trade > 0 ? `, ${trade} for trade` : ''}`}
        {owned?.attributes.field_binder_location ? ` (${owned.attributes.field_binder_location})` : ''}
      </p>

      {wishes.length > 0 && (
        <ul style={{ margin: '0 0 0.4rem', paddingLeft: '1.1rem' }}>
          {wishes.map(w => (
            <li key={w.id}>
              Wanted: {w.quantity}x {w.anyPrinting ? 'any printing' : 'this printing'}
              {w.foil ? ', foil' : ''}
              {w.intent ? ` · ${w.intent.name}` : ''}
              {w.deck ? ` · ${w.deck.title}` : ''}
              {' · '}
              {w.done ? 'covered by your collection' : `you have ${w.owned}`}{' '}
              <button type="button" onClick={() => remove.mutate(w.id)} style={{ marginLeft: 4 }}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {!open ? (
        <button type="button" onClick={() => setOpen(true)}>
          Add {cardTitle} to wishlist
        </button>
      ) : (
        <form
          onSubmit={e => {
            e.preventDefault();
            save.mutate();
          }}
          style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.3rem 0.5rem', maxWidth: 420 }}
        >
          <label htmlFor="wish-qty">Quantity</label>
          <input
            id="wish-qty"
            type="number"
            min={1}
            value={quantity}
            onChange={e => setQuantity(Math.max(1, Number.parseInt(e.target.value, 10) || 1))}
            style={{ ...fieldStyle, width: 60 }}
          />

          <span>Printing</span>
          <label>
            <input type="checkbox" checked={anyPrinting} onChange={e => setAnyPrinting(e.target.checked)} /> Any
            printing (off: only this one)
          </label>

          <span>Foil</span>
          <label>
            <input type="checkbox" checked={foil} onChange={e => setFoil(e.target.checked)} /> Foil only
          </label>

          <label htmlFor="wish-intent">Intent</label>
          <select id="wish-intent" value={intentId} onChange={e => setIntentId(e.target.value)} style={fieldStyle}>
            <option value="">None</option>
            {intents.map(i => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </select>

          <label htmlFor="wish-deck" title="The card also goes on this deck's maybeboard. Fixed once saved.">
            Deck
          </label>
          <select id="wish-deck" value={deckId} onChange={e => setDeckId(e.target.value)} style={fieldStyle}>
            <option value="">None</option>
            {decks.map(d => (
              <option key={d.id} value={d.id}>
                {d.attributes.title}
              </option>
            ))}
          </select>

          <label htmlFor="wish-condition">Min. condition</label>
          <select
            id="wish-condition"
            value={minCondition}
            onChange={e => setMinCondition(e.target.value)}
            style={fieldStyle}
          >
            <option value="">Any</option>
            {WISH_CONDITIONS.map(c => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          <label htmlFor="wish-notes">Notes</label>
          <input id="wish-notes" type="text" value={notes} onChange={e => setNotes(e.target.value)} style={fieldStyle} />

          <span />
          <div style={{ display: 'flex', gap: 6 }}>
            <button type="submit" disabled={save.isPending}>
              {save.isPending ? 'Saving...' : 'Save wish'}
            </button>
            <button type="button" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <Link href="/wishlist" style={{ color: 'var(--accent)', alignSelf: 'center' }}>
              Open wishlist
            </Link>
          </div>
          {error != null && (
            <p role="alert" style={{ gridColumn: '1 / -1', color: '#c00', margin: 0 }}>
              {error}
            </p>
          )}
        </form>
      )}
    </section>
  );
};

export default WishlistPanel;
