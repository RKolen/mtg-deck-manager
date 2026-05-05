/**
 * Client for the AI Deck Coach endpoint (POST /api/deck-coach).
 *
 * Sends pre-computed analysis metrics to Drupal/Ollama and returns a
 * plain-language coaching paragraph. All numbers come from deckAnalysis.ts
 * so no extra Drupal round-trip is needed for the data itself.
 */

import { createDrupalClient } from './httpClient';

const client = createDrupalClient('/api');

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DeckCoachMetrics {
  avgCmc: number;
  landCount: number;
  totalManaSources: number;
  /** Percentage of effective mana sources per colour (0-100). */
  colorSourcePct: Record<string, number>;
  /** Percentage of coloured pip demand per colour (0-100). */
  colorPipPct: Record<string, number>;
  /** Cards at each CMC, keyed by CMC as a string. "7+" for CMC ≥ 7. */
  cmcHistogram: Record<string, number>;
  /** P(≥1 source) by turn 2 and turn 3 per colour. */
  manaHandProb: Record<string, { turn2: number; turn3: number }>;
  manaSources: {
    lands: number;
    nonLandProducers: number;
    /** Card types of non-land mana producers, e.g. ["creature", "artifact"]. */
    producerTypes: string[];
  };
}

export interface DeckCoachRequest {
  format: string;
  deckTitle: string;
  metrics: DeckCoachMetrics;
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

/**
 * Fetches coaching commentary for a deck based on its analysis metrics.
 *
 * @returns Plain-text coaching response from Ollama (four paragraphs).
 */
export async function fetchDeckCoaching(req: DeckCoachRequest): Promise<string> {
  const response = await client.post<{ coaching: string }>(
    '/deck-coach',
    req,
    { headers: { 'Content-Type': 'application/json', Accept: 'application/json' } },
  );
  return response.data.coaching;
}
