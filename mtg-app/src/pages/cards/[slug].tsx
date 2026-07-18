/**
 * Card detail page.
 *
 * Route: /cards/:slug  (Next.js dynamic route via [slug].tsx)
 *
 * The slug is derived from the card title using the shared slugify utility,
 * e.g. "Monastery Swiftspear" -> /cards/monastery-swiftspear.
 * The page resolves the slug back to a Drupal mtg_card node via a
 * STARTS_WITH title filter + client-side slug match.
 */

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useQuery } from '@tanstack/react-query';
import { fetchCardBySlug } from '../../services/drupalApi';

const CardPage: React.FC = () => {
  const router = useRouter();
  const slug = typeof router.query.slug === 'string' ? router.query.slug : '';

  const { data: card, isLoading, isError } = useQuery({
    queryKey: ['card', slug],
    queryFn: () => fetchCardBySlug(slug),
    enabled: router.isReady && slug !== '',
    staleTime: 5 * 60_000,
  });

  if (isLoading) {
    return (
      <main style={{ padding: '1.5rem' }}>
        <p>Loading card...</p>
      </main>
    );
  }

  if (isError || card == null) {
    return (
      <main style={{ padding: '1.5rem' }}>
        <p style={{ color: '#c00' }}>Card not found.</p>
        <p>
          <Link href="/decks">Back to decks</Link>
        </p>
      </main>
    );
  }

  const attrs = card.attributes;

  const oracleText =
    attrs.field_oracle_text != null
      ? typeof attrs.field_oracle_text === 'string'
        ? attrs.field_oracle_text
        : attrs.field_oracle_text.value
      : null;

  const isCreature =
    attrs.field_type_line != null &&
    attrs.field_type_line.includes('Creature');

  const isPlaneswalker =
    attrs.field_type_line != null &&
    attrs.field_type_line.includes('Planeswalker');

  return (
    <main
      style={{
        padding: '1.5rem',
        maxWidth: 760,
        color: 'var(--ink)',
        background: 'var(--bg)',
      }}
    >
      <p style={{ margin: '0 0 1.25rem' }}>
        <Link href="/decks" style={{ color: 'var(--accent)' }}>
          Back to decks
        </Link>
      </p>

      <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
        {/* Card image */}
        {attrs.field_image_uri != null && attrs.field_image_uri !== '' && (
          <img
            src={attrs.field_image_uri}
            alt={attrs.title}
            style={{
              width: 265,
              borderRadius: 12,
              alignSelf: 'flex-start',
              flexShrink: 0,
            }}
          />
        )}

        {/* Card text — ink on bg so light/dark themes both stay readable */}
        <div style={{ flex: 1, minWidth: 220, color: 'var(--ink)' }}>
          <h1 style={{ margin: '0 0 0.25rem', color: 'var(--ink)' }}>{attrs.title}</h1>

          {attrs.field_mana_cost != null && attrs.field_mana_cost !== '' && (
            <p style={{ margin: '0 0 0.25rem', fontSize: '1.05rem', color: 'var(--ink)' }}>
              {attrs.field_mana_cost}
              {attrs.field_cmc != null && (
                <span style={{ marginLeft: 8, color: 'var(--ink)', fontSize: '0.9rem' }}>
                  (CMC {attrs.field_cmc})
                </span>
              )}
            </p>
          )}

          {attrs.field_type_line != null && (
            <p
              style={{
                margin: '0 0 0.75rem',
                fontStyle: 'italic',
                color: 'var(--ink)',
              }}
            >
              {attrs.field_type_line}
            </p>
          )}

          {oracleText != null && oracleText !== '' && (
            <p
              style={{
                whiteSpace: 'pre-wrap',
                background: 'var(--bg-2)',
                color: 'var(--ink)',
                border: '1px solid var(--line)',
                padding: '0.6rem 0.75rem',
                borderRadius: 4,
                fontSize: '0.95rem',
                margin: '0 0 0.75rem',
                lineHeight: 1.5,
              }}
            >
              {oracleText}
            </p>
          )}

          {isCreature &&
            (attrs.field_power != null || attrs.field_toughness != null) && (
              <p style={{ margin: '0 0 0.5rem', fontWeight: 'bold', color: 'var(--ink)' }}>
                {attrs.field_power ?? '?'} / {attrs.field_toughness ?? '?'}
              </p>
            )}

          {isPlaneswalker && attrs.field_loyalty != null && (
            <p style={{ margin: '0 0 0.5rem', fontWeight: 'bold', color: 'var(--ink)' }}>
              Loyalty: {attrs.field_loyalty}
            </p>
          )}

          {attrs.field_colors != null && attrs.field_colors.length > 0 && (
            <p style={{ margin: '0 0 0.25rem', fontSize: '0.875rem', color: 'var(--ink)' }}>
              <strong>Colors:</strong> {attrs.field_colors.join(', ')}
            </p>
          )}

          {attrs.field_is_mana_producer === true &&
            attrs.field_produced_mana != null &&
            attrs.field_produced_mana.length > 0 && (
              <p style={{ margin: '0 0 0.25rem', fontSize: '0.875rem', color: 'var(--ink)' }}>
                <strong>Produces:</strong> {attrs.field_produced_mana.join(', ')}
              </p>
            )}

          {attrs.field_legal_formats != null &&
            attrs.field_legal_formats.length > 0 && (
              <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: 'var(--ink)' }}>
                <strong>Legal in:</strong> {attrs.field_legal_formats.join(', ')}
              </p>
            )}
        </div>
      </div>
    </main>
  );
};

export const getServerSideProps = async () => ({ props: {} });

export default CardPage;
