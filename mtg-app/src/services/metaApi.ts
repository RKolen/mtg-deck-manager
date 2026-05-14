/**
 * Clients for Phase 10A — Pro Meta Analyst.
 *
 * Three backends:
 *   Drupal GraphQL   — meta_deck node catalogue  (/graphql)
 *   Drupal REST      — POST /api/matchup-advice  (LLM matchup advisor)
 *   Python service   — POST /classify            (deck deduction classifier)
 */

import axios from 'axios';
import { gql } from 'graphql-request';
import { createDrupalClient } from './httpClient';
import { getGraphQLClient } from './graphqlClient';
import type { JsonApiResource } from '../types/drupal';

const drupalApi = createDrupalClient('/api');

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MetaDeckAttributes {
  title: string;
  field_format: string;
  field_meta_share: string | null;
  field_archetype_tags: string[];
  field_fetched_at: string | null;
}

export type MetaDeck = JsonApiResource<MetaDeckAttributes>;

export interface MatchupAdviceRequest {
  playerDeckId: number;
  opponentArchetype: string;
  confidence: number;
  format: string;
}

export interface MatchupAdvice {
  dynamic: string;
  threats: string[];
  sideboard: { in: string[]; out: string[] };
  keyPlay: string;
}

export interface Play {
  card_name: string;
  type?: string;
  colors?: string[];
}

export interface ArchetypeProbability {
  name: string;
  probability: number;
}

// ---------------------------------------------------------------------------
// Meta deck catalogue
// ---------------------------------------------------------------------------

interface GqlMetaDeck {
  id: string;
  title: string;
  format: string;
  metaShare: number | null;
  archetypeTags: string[];
  fetchedAt: string | null;
}

function toMetaDeck(d: GqlMetaDeck): MetaDeck {
  return {
    id: d.id,
    type: 'node--meta_deck',
    attributes: {
      title: d.title,
      field_format: d.format,
      field_meta_share: d.metaShare != null ? String(d.metaShare) : null,
      field_archetype_tags: d.archetypeTags,
      field_fetched_at: d.fetchedAt,
    },
  };
}

/**
 * Fetches all meta_deck nodes for a given format via GraphQL, sorted by meta share desc.
 */
export async function fetchMetaDecks(format: string): Promise<MetaDeck[]> {
  const query = gql`
    query GetMetaDecks($format: String!) {
      metaDecks(format: $format) {
        id title format metaShare archetypeTags fetchedAt
      }
    }
  `;
  const data = await getGraphQLClient().request<{ metaDecks: GqlMetaDeck[] }>(query, { format });
  return data.metaDecks.map(toMetaDeck);
}

// ---------------------------------------------------------------------------
// Matchup advisor
// ---------------------------------------------------------------------------

/**
 * Fetches LLM-generated matchup advice from Drupal/Ollama.
 */
export async function fetchMatchupAdvice(req: MatchupAdviceRequest): Promise<MatchupAdvice> {
  const response = await drupalApi.post<MatchupAdvice>('/matchup-advice', req, {
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
  });
  return response.data;
}

// ---------------------------------------------------------------------------
// Deck deduction classifier (Python service on host)
// ---------------------------------------------------------------------------

const CLASSIFIER_URL =
  process.env.GATSBY_CLASSIFIER_URL ?? 'http://localhost:8001';

const classifierClient = axios.create({ baseURL: CLASSIFIER_URL, timeout: 10_000 });

/**
 * Returns P(archetype) for each known archetype given observed plays.
 * Returns an empty array if the classifier service is not running.
 */
export async function classifyPlays(plays: Play[]): Promise<ArchetypeProbability[]> {
  try {
    const response = await classifierClient.post<{ archetypes: ArchetypeProbability[] }>(
      '/classify',
      { plays },
    );
    return response.data.archetypes;
  } catch {
    return [];
  }
}
