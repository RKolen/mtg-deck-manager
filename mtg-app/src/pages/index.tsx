/**
 * Home — CMS body from Drupal when present, plus live deck count.
 * No mock ticker / movers / activity (those have no backend yet).
 */

import React from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { gql } from 'graphql-request';
import parse from 'html-react-parser';
import { getGraphQLClient } from '../services/graphqlClient';
import { fetchDecks, fetchCollectionValue } from '../services/drupalApi';
import { useTheme } from '../context/ThemeContext';
import { Stat } from '../components/design/Panel';
import { formatPrice, priceSourceLabel } from '../utils/prices';
import { slugify } from '../utils/slugify';

interface PageNode {
  id: string;
  title: string;
  body?: string | null;
  pathAlias?: string | null;
}

async function fetchPages(): Promise<PageNode[]> {
  const data = await getGraphQLClient().request<{ pages: PageNode[] }>(gql`
    query { pages { id title body pathAlias } }
  `);
  return data.pages;
}

const IndexPage: React.FC = () => {
  const { currency } = useTheme();
  const { data: pages = [] } = useQuery({ queryKey: ['pages'], queryFn: fetchPages });
  const { data: decks = [] } = useQuery({ queryKey: ['decks'], queryFn: fetchDecks });
  const { data: collectionValue = null } = useQuery({
    queryKey: ['collectionValue'],
    queryFn: fetchCollectionValue,
  });

  const page = pages.find(n => n.pathAlias === '/') ?? pages[0] ?? null;

  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      <div
        style={{
          padding: '24px 28px',
          borderBottom: '1px solid var(--line)',
          background: 'var(--bg-1)',
        }}
      >
        <div className="mono uc dim" style={{ fontSize: 10, marginBottom: 8 }}>
          HOME
        </div>
        <h1
          className="sans"
          style={{ margin: 0, fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em' }}
        >
          {page?.title ?? 'MTG Deck Manager'}
        </h1>
        {page?.body != null && (
          <div
            className="mono"
            style={{ marginTop: 12, color: 'var(--ink-2)', maxWidth: 640, lineHeight: 1.6 }}
          >
            {parse(page.body)}
          </div>
        )}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 16,
          padding: 20,
          borderBottom: '1px solid var(--line)',
        }}
      >
        <Stat label="DECKS" value={decks.length} sub="from Drupal" />
        <Stat
          label="COLLECTION"
          value={formatPrice(collectionValue, currency)}
          sub={priceSourceLabel(currency)}
          accent
        />
        <Stat label="FORMATS" value={new Set(decks.map(d => d.attributes.field_format)).size || '--'} sub="in library" />
      </div>

      <div style={{ padding: 20, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div>
          <div className="mono uc dim" style={{ fontSize: 9, marginBottom: 8 }}>
            RECENT DECKS
          </div>
          {decks.length === 0 ? (
            <div className="mono dim">No decks in Drupal yet.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {decks.slice(0, 8).map(d => (
                <Link
                  key={d.id}
                  href={`/decks/${slugify(d.attributes.title)}`}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '8px 10px',
                    background: 'var(--bg-2)',
                    borderLeft: '2px solid var(--accent)',
                    textDecoration: 'none',
                    color: 'var(--ink)',
                    fontFamily: 'var(--mono)',
                    fontSize: 12,
                  }}
                >
                  <span style={{ fontWeight: 600 }}>{d.attributes.title}</span>
                  <span className="dim">{d.attributes.field_format}</span>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="mono uc dim" style={{ fontSize: 9, marginBottom: 8 }}>
            JUMP
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {[
              ['/decks', 'Deck library'],
              ['/collection', 'Collection'],
              ['/import', 'Import XLSX'],
              ['/meta-decks', 'Meta decks'],
              ['/play', 'Playtest'],
            ].map(([href, label]) => (
              <Link
                key={href}
                href={href}
                style={{
                  padding: '8px 10px',
                  border: '1px solid var(--line)',
                  textDecoration: 'none',
                  color: 'var(--ink-2)',
                  fontFamily: 'var(--mono)',
                  fontSize: 12,
                }}
              >
                {label} <span className="dim">→</span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default IndexPage;
