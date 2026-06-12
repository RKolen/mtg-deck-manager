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

const CollectionCardPage: React.FC = () => {
  const router = useRouter();
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
    mutationFn: ({ owned, foil }: { owned: number; foil: number }) =>
      upsertCollectionCard(
        cardId!,
        card!.attributes.title,
        owned,
        foil,
        cc?.id,
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['collectionCard', cardId] }),
  });

  const owned = cc?.attributes.field_quantity_owned ?? 0;
  const foil = cc?.attributes.field_quantity_foil ?? 0;

  if (cardLoading || ccLoading) {
    return <main style={{ padding: '1.5rem' }}>Loading...</main>;
  }
  if (card == null) {
    return <main style={{ padding: '1.5rem' }}>Card not found.</main>;
  }

  const a = card.attributes;
  const oracleText =
    typeof a.field_oracle_text === 'string'
      ? a.field_oracle_text
      : (a.field_oracle_text as { value?: string } | null)?.value ?? '';

  return (
    <main style={{ padding: '1.5rem', maxWidth: 700 }}>
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/collection">Back to collection</Link>
      </p>

      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
        {a.field_image_uri != null && (
          <img
            src={a.field_image_uri}
            alt={a.title}
            style={{ width: 240, borderRadius: 8, flexShrink: 0 }}
          />
        )}

        <div style={{ flex: 1, minWidth: 220 }}>
          <h1 style={{ marginTop: 0, marginBottom: '0.25rem' }}>{a.title}</h1>
          <p style={{ margin: '0 0 0.25rem', color: '#666' }}>
            {a.field_type_line}
            {a.field_mana_cost != null && a.field_mana_cost !== '' && (
              <span style={{ marginLeft: 8 }}>{a.field_mana_cost}</span>
            )}
          </p>
          {oracleText !== '' && (
            <p style={{ margin: '0.5rem 0', fontSize: '0.875rem', whiteSpace: 'pre-line' }}>
              {oracleText}
            </p>
          )}
          {(a.field_power != null || a.field_toughness != null) && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.875rem' }}>
              {a.field_power}/{a.field_toughness}
            </p>
          )}
          {a.field_set_name != null && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.8rem', color: '#888' }}>
              {a.field_set_name} · {a.field_rarity} · #{a.field_collector_number}
            </p>
          )}
          {(a.field_price_usd != null || a.field_price_usd_foil != null) && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.8rem', color: '#555' }}>
              {a.field_price_usd != null && `$${a.field_price_usd}`}
              {a.field_price_usd_foil != null && ` · foil $${a.field_price_usd_foil}`}
            </p>
          )}

          <hr style={{ margin: '1rem 0' }} />

          <h2 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>My collection</h2>

          <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: '0.8rem', color: '#666' }}>Regular</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button
                  type="button"
                  style={{ width: 28 }}
                  disabled={owned <= 0}
                  onClick={() => upsert.mutate({ owned: owned - 1, foil })}
                >
                  -
                </button>
                <span style={{ minWidth: 24, textAlign: 'center', fontWeight: 'bold' }}>
                  {owned}
                </span>
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
              <span style={{ fontSize: '0.8rem', color: '#666' }}>Foil</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button
                  type="button"
                  style={{ width: 28 }}
                  disabled={foil <= 0}
                  onClick={() => upsert.mutate({ owned, foil: foil - 1 })}
                >
                  -
                </button>
                <span style={{ minWidth: 24, textAlign: 'center', fontWeight: 'bold' }}>
                  {foil}
                </span>
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
            <p style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: '#555' }}>
              Total: {owned + foil} ({owned} regular, {foil} foil)
            </p>
          )}
        </div>
      </div>
    </main>
  );
};

export const getServerSideProps = async () => ({ props: {} });

export default CollectionCardPage;
