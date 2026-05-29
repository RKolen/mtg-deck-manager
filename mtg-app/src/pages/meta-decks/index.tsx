/**
 * Meta Decks page.
 *
 * Lists meta archetypes for a chosen format, fetched via GraphQL.
 * A "Scrape" button per format triggers the PHP scraper in Drupal,
 * which upserts meta_deck nodes directly through the entity API.
 * Decks that have fallen out of the meta are never deleted.
 */

import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { gql } from 'graphql-request';
import { getGraphQLClient } from '../../services/graphqlClient';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MtgFormat {
  name: string;
  slug: string;
}

interface MetaDeck {
  id: string;
  title: string;
  format: string;
  metaShare: number | null;
  archetypeTags: string[];
  fetchedAt: string | null;
}

interface ScrapeResult {
  format: string;
  created: number;
  updated: number;
  skipped: number;
}

// ---------------------------------------------------------------------------
// GraphQL queries / mutations
// ---------------------------------------------------------------------------

const FORMATS_QUERY = gql`
  query {
    formats {
      name
      slug
    }
  }
`;

const META_DECKS_QUERY = gql`
  query MetaDecks($format: String!) {
    metaDecks(format: $format) {
      id
      title
      format
      metaShare
      archetypeTags
      fetchedAt
    }
  }
`;

const SCRAPE_MUTATION = gql`
  mutation ScrapeMetaDecks($format: String!, $limit: Int) {
    scrapeMetaDecks(format: $format, limit: $limit) {
      format
      created
      updated
      skipped
    }
  }
`;

// ---------------------------------------------------------------------------
// Data fetchers
// ---------------------------------------------------------------------------

async function fetchFormats(): Promise<MtgFormat[]> {
  const data = await getGraphQLClient().request<{ formats: MtgFormat[] }>(FORMATS_QUERY);
  return data.formats;
}

async function fetchMetaDecks(format: string): Promise<MetaDeck[]> {
  const data = await getGraphQLClient().request<{ metaDecks: MetaDeck[] }>(
    META_DECKS_QUERY,
    { format },
  );
  return data.metaDecks;
}

async function runScrape(format: string, limit: number): Promise<ScrapeResult> {
  const data = await getGraphQLClient().request<{ scrapeMetaDecks: ScrapeResult }>(
    SCRAPE_MUTATION,
    { format, limit },
  );
  return data.scrapeMetaDecks;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const MetaDecksPage: React.FC = () => {
  const qc = useQueryClient();
  const [selectedFormat, setSelectedFormat] = useState<string | null>(null);
  const [scrapeLimit, setScrapeLimit] = useState(20);
  const [lastResult, setLastResult] = useState<ScrapeResult | null>(null);
  const [scrapeError, setScrapeError] = useState<string | null>(null);

  const { data: formats = [], isLoading: formatsLoading } = useQuery<MtgFormat[]>({
    queryKey: ['formats'],
    queryFn: fetchFormats,
  });

  useEffect(() => {
    if (selectedFormat === null && formats.length > 0 && formats[0] != null) {
      setSelectedFormat(formats[0].name);
    }
  }, [formats, selectedFormat]);

  const { data: decks = [], isLoading: decksLoading } = useQuery<MetaDeck[]>({
    queryKey: ['metaDecks', selectedFormat],
    queryFn: () => fetchMetaDecks(selectedFormat as string),
    enabled: selectedFormat !== null,
  });

  const scrapeMutation = useMutation({
    mutationFn: () => runScrape(selectedFormat as string, scrapeLimit),
    onSuccess: (result) => {
      setLastResult(result);
      setScrapeError(null);
      qc.invalidateQueries({ queryKey: ['metaDecks', selectedFormat] });
    },
    onError: (err: unknown) => {
      setScrapeError(err instanceof Error ? err.message : 'Scrape failed.');
      setLastResult(null);
    },
  });

  const isScraping = scrapeMutation.isPending ?? false;

  return (
    <main style={{ padding: '1.5rem', maxWidth: 900 }}>
      <h1 style={{ marginTop: 0 }}>Meta Decks</h1>

      <nav style={{ marginBottom: '1.5rem' }}>
        <a href="/" style={{ marginRight: '1rem' }}>Home</a>
      </nav>

      {formatsLoading && <p>Loading formats...</p>}

      {/* Format selector + scrape controls */}
      {formats.length > 0 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            flexWrap: 'wrap',
            marginBottom: '1rem',
          }}
        >
          <label htmlFor="format-select" style={{ fontWeight: 'bold' }}>
            Format:
          </label>
          <select
            id="format-select"
            value={selectedFormat ?? ''}
            onChange={(e) => {
              setSelectedFormat(e.target.value);
              setLastResult(null);
              setScrapeError(null);
            }}
          >
            {formats.map((f) => (
              <option key={f.slug} value={f.name}>
                {f.name}
              </option>
            ))}
          </select>

          <label htmlFor="limit-input">Limit:</label>
          <input
            id="limit-input"
            type="number"
            min={1}
            max={50}
            value={scrapeLimit}
            onChange={(e) => setScrapeLimit(Math.max(1, parseInt(e.target.value, 10) || 20))}
            style={{ width: '4rem' }}
          />

          <button
            type="button"
            disabled={selectedFormat === null || isScraping}
            onClick={() => {
              setLastResult(null);
              setScrapeError(null);
              scrapeMutation.mutate();
            }}
          >
            {isScraping ? 'Scraping...' : 'Scrape MTGGoldfish'}
          </button>
        </div>
      )}

      {/* Feedback */}
      {lastResult !== null && (
        <p style={{ color: 'green' }}>
          {lastResult.format}: {lastResult.created} created, {lastResult.updated} updated,{' '}
          {lastResult.skipped} skipped.
        </p>
      )}
      {scrapeError !== null && (
        <p style={{ color: 'red' }}>Error: {scrapeError}</p>
      )}

      {/* Deck table */}
      {decksLoading && <p>Loading decks...</p>}

      {!decksLoading && decks.length === 0 && selectedFormat !== null && (
        <p>No meta decks for {selectedFormat} yet. Use the Scrape button above.</p>
      )}

      {decks.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #ccc', textAlign: 'left' }}>
              <th style={{ padding: '0.4rem 0.6rem' }}>Archetype</th>
              <th style={{ padding: '0.4rem 0.6rem' }}>Meta Share</th>
              <th style={{ padding: '0.4rem 0.6rem' }}>Tags</th>
              <th style={{ padding: '0.4rem 0.6rem' }}>Fetched At</th>
            </tr>
          </thead>
          <tbody>
            {decks.map((deck) => (
              <tr key={deck.id} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '0.4rem 0.6rem', fontWeight: 'bold' }}>{deck.title}</td>
                <td style={{ padding: '0.4rem 0.6rem' }}>
                  {deck.metaShare !== null ? `${deck.metaShare}%` : '-'}
                </td>
                <td style={{ padding: '0.4rem 0.6rem' }}>
                  {deck.archetypeTags.join(', ')}
                </td>
                <td style={{ padding: '0.4rem 0.6rem', color: '#666' }}>
                  {deck.fetchedAt !== null ? new Date(deck.fetchedAt).toLocaleDateString() : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
};

export default MetaDecksPage;
