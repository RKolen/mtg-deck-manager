/**
 * Individual collection card page.
 * Route: /collection/card/:id  where :id is slugify(card.title)
 */

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchCardBySlug,
  fetchCollectionCardByCardId,
  upsertCollectionCard,
} from '../../../services/drupalApi';
import { invalidateInventoryQueries, patchCollectionRow } from '../../../services/queryCache';
import WishlistPanel from '../../../components/WishlistPanel';
import { getOracleText } from '../../../utils/deckAnalysis';
import { slugify } from '../../../utils/slugify';
import { formatPrice, priceFor } from '../../../utils/prices';
import { useTheme } from '../../../context/ThemeContext';

const CollectionCardPage: React.FC = () => {
  const router = useRouter();
  const { currency } = useTheme();
  const slug = typeof router.query.id === 'string' ? router.query.id : '';
  const qc = useQueryClient();

  const { data: card, isLoading: cardLoading } = useQuery({
    queryKey: ['card', slug],
    queryFn: () => fetchCardBySlug(slug),
    enabled: router.isReady && slug !== '',
  });

  const cardId = card?.id;

  const { data: cc, isLoading: ccLoading } = useQuery({
    queryKey: ['collectionCard', cardId],
    queryFn: () => fetchCollectionCardByCardId(cardId!),
    enabled: cardId != null,
  });

  const upsert = useMutation({
    mutationFn: ({
      owned,
      foil,
      trade,
    }: {
      owned: number;
      foil: number;
      trade?: { quantityTrade?: number; binderLocation?: string };
    }) =>
      upsertCollectionCard(
        cardId!,
        card!.attributes.title,
        owned,
        foil,
        cc?.id,
        trade,
      ),
    onSuccess: (saved, { owned, foil, trade }) => {
      // Update this row in the cached collection list instead of reloading it.
      const patched =
        cardId != null
        && patchCollectionRow(qc, {
          cardId,
          id: saved.id,
          quantityOwned: owned,
          quantityFoil: foil,
          quantityTrade: trade?.quantityTrade,
          binderLocation: trade?.binderLocation,
        });
      void invalidateInventoryQueries(qc, { keepCollectionList: patched });
    },
  });

  const owned = cc?.attributes.field_quantity_owned ?? 0;
  const foil = cc?.attributes.field_quantity_foil ?? 0;
  const trade = cc?.attributes.field_quantity_trade ?? 0;
  const binderLocation = cc?.attributes.field_binder_location ?? '';

  if (cardLoading || ccLoading) {
    return <main style={{ padding: '1.5rem' }}>Loading...</main>;
  }
  if (card == null) {
    return <main style={{ padding: '1.5rem' }}>Card not found.</main>;
  }

  const a = card.attributes;
  const oracleText = getOracleText(a);

  return (
    <main
      style={{
        padding: '1.5rem',
        maxWidth: 700,
        color: 'var(--ink)',
        background: 'var(--bg)',
      }}
    >
      <p style={{ margin: '0 0 1rem', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <Link href="/collection" style={{ color: 'var(--accent)' }}>
          Back to collection
        </Link>
        <Link
          href={`/cards/${slugify(a.title)}${card.id ? `?printing=${card.id}` : ''}`}
          style={{ color: 'var(--accent)' }}
        >
          All printings
        </Link>
      </p>

      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
        {a.field_image_uri != null && (
          <img
            src={a.field_image_uri}
            alt={a.title}
            style={{ width: 240, borderRadius: 8, flexShrink: 0 }}
          />
        )}

        <div style={{ flex: 1, minWidth: 220, color: 'var(--ink)' }}>
          <h1 style={{ marginTop: 0, marginBottom: '0.25rem', color: 'var(--ink)' }}>
            {a.title}
          </h1>
          <p style={{ margin: '0 0 0.25rem', color: 'var(--ink)' }}>
            {a.field_type_line}
            {a.field_mana_cost != null && a.field_mana_cost !== '' && (
              <span style={{ marginLeft: 8 }}>{a.field_mana_cost}</span>
            )}
          </p>
          {oracleText !== '' && (
            <p
              style={{
                margin: '0.5rem 0',
                fontSize: '0.875rem',
                whiteSpace: 'pre-line',
                color: 'var(--ink)',
                background: 'var(--bg-2)',
                border: '1px solid var(--line)',
                padding: '0.6rem 0.75rem',
                borderRadius: 4,
              }}
            >
              {oracleText}
            </p>
          )}
          {(a.field_power != null || a.field_toughness != null) && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.875rem', color: 'var(--ink)' }}>
              {a.field_power}/{a.field_toughness}
            </p>
          )}
          {a.field_set_name != null && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.8rem', color: 'var(--ink)' }}>
              {a.field_set_name} · {a.field_rarity} · #{a.field_collector_number}
            </p>
          )}
          {(priceFor(a, currency) != null || priceFor(a, currency, true) != null) && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.8rem', color: 'var(--ink)' }}>
              {priceFor(a, currency) != null && formatPrice(priceFor(a, currency), currency)}
              {priceFor(a, currency, true) != null && ` · foil ${formatPrice(priceFor(a, currency, true), currency)}`}
            </p>
          )}

          <hr style={{ margin: '1rem 0', borderColor: 'var(--line)' }} />

          <h2 style={{ margin: '0 0 0.75rem', fontSize: '1rem', color: 'var(--ink)' }}>
            My collection
          </h2>
          <p style={{ margin: '0 0 0.75rem', fontSize: '0.8rem', color: 'var(--ink)', opacity: 0.85 }}>
            Regular and foil are counted separately. Total = regular + foil.
          </p>

          <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--ink)' }}>Regular (non-foil)</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button
                  type="button"
                  style={{ width: 28 }}
                  disabled={owned <= 0}
                  onClick={() => upsert.mutate({ owned: owned - 1, foil })}
                >
                  -
                </button>
                <input
                  type="number"
                  min={0}
                  value={owned}
                  onChange={e =>
                    upsert.mutate({
                      owned: Math.max(0, Number.parseInt(e.target.value, 10) || 0),
                      foil,
                    })
                  }
                  style={{
                    width: 48,
                    textAlign: 'center',
                    color: '#000',
                    background: '#fff',
                    border: '1px solid #000',
                    padding: '2px 4px',
                  }}
                />
                <button
                  type="button"
                  style={{ width: 28 }}
                  onClick={() => upsert.mutate({ owned: owned + 1, foil })}
                >
                  +
                </button>
              </div>
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--ink)' }}>Foil</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button
                  type="button"
                  style={{ width: 28 }}
                  disabled={foil <= 0}
                  onClick={() => upsert.mutate({ owned, foil: foil - 1 })}
                >
                  -
                </button>
                <input
                  type="number"
                  min={0}
                  value={foil}
                  onChange={e =>
                    upsert.mutate({
                      owned,
                      foil: Math.max(0, Number.parseInt(e.target.value, 10) || 0),
                    })
                  }
                  style={{
                    width: 48,
                    textAlign: 'center',
                    color: '#000',
                    background: '#fff',
                    border: '1px solid #000',
                    padding: '2px 4px',
                  }}
                />
                <button
                  type="button"
                  style={{ width: 28 }}
                  onClick={() => upsert.mutate({ owned, foil: foil + 1 })}
                >
                  +
                </button>
              </div>
            </label>
          </div>

          {(owned > 0 || foil > 0) && (
            <p style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: 'var(--ink)' }}>
              Total: {owned + foil} ({owned} regular, {foil} foil)
            </p>
          )}

          {(owned > 0 || foil > 0) && (
            <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'flex-end', flexWrap: 'wrap', marginTop: '0.5rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--ink)' }}>For trade</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <button
                    type="button"
                    style={{ width: 28 }}
                    disabled={trade <= 0}
                    onClick={() => upsert.mutate({ owned, foil, trade: { quantityTrade: trade - 1 } })}
                  >
                    -
                  </button>
                  <span style={{ width: 48, textAlign: 'center' }}>{trade}</span>
                  <button
                    type="button"
                    style={{ width: 28 }}
                    disabled={trade >= owned + foil}
                    onClick={() => upsert.mutate({ owned, foil, trade: { quantityTrade: trade + 1 } })}
                  >
                    +
                  </button>
                </div>
              </div>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1, minWidth: 180 }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--ink)' }}>Binder location</span>
                <input
                  key={binderLocation}
                  type="text"
                  defaultValue={binderLocation}
                  placeholder="e.g. Trade binder, page 3, pocket 7"
                  onBlur={e => {
                    if (e.target.value !== binderLocation) {
                      upsert.mutate({ owned, foil, trade: { binderLocation: e.target.value } });
                    }
                  }}
                  style={{ color: '#000', background: '#fff', border: '1px solid #000', padding: '2px 4px' }}
                />
              </label>
            </div>
          )}

          {cardId != null && <WishlistPanel key={cardId} cardId={cardId} cardTitle={a.title} />}
        </div>
      </div>
    </main>
  );
};

export const getServerSideProps = async () => ({ props: {} });

export default CollectionCardPage;
