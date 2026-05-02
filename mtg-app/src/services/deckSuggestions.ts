/**
 * Typed client for the MTG Card Suggestions REST endpoint.
 *
 * GET /api/card-suggestions?deck_id=<nid>&limit=<n>
 *
 * Returns a ranked list of cards that synergise with the given deck,
 * derived from Milvus semantic search + Ollama reasoning.
 */

import { createDrupalClient } from './httpClient';

const client = createDrupalClient('/api');

export interface SuggestedCard {
  nid: number;
  name: string;
  score: number;
}

export interface CardSuggestion {
  card: SuggestedCard;
  reason: string;
  score: number;
}

export interface CardSuggestionsResponse {
  data: CardSuggestion[];
  meta: { count: number };
}

/**
 * Fetches AI-powered card suggestions for a deck.
 *
 * @param deckNid - The Drupal node ID of the deck.
 * @param limit   - Max number of suggestions to return (1–50, default 10).
 */
export async function fetchCardSuggestions(
  deckNid: number,
  limit = 10,
): Promise<CardSuggestion[]> {
  const response = await client.get<CardSuggestionsResponse>(
    '/card-suggestions',
    {
      params: { deck_id: deckNid, limit },
      headers: { Accept: 'application/json' },
    },
  );
  return response.data.data;
}
