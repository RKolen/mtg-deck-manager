/**
 * Client for the MTG Card Search REST endpoint (/api/card-search).
 *
 * Backed by Search API + Solr on the Drupal side. The response shape mirrors
 * the JSON:API structure so existing JsonApiResource types can be reused.
 */

import axios, { type AxiosInstance } from 'axios';
import type { JsonApiResource, MtgCardAttributes } from '../types/drupal';

const DRUPAL_URL = process.env.GATSBY_DRUPAL_URL ?? 'https://mtg-deck-manager.ddev.site';

const client: AxiosInstance = axios.create({
  baseURL: `${DRUPAL_URL}/api`,
  auth: {
    username: process.env.GATSBY_DRUPAL_USER ?? 'admin',
    password: process.env.GATSBY_DRUPAL_PASS ?? 'admin',
  },
});

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CardSearchParams {
  /** Full-text search against card name and oracle text. */
  q?: string;
  /** Filter by type line (partial match). */
  type?: string;
  /** Filter by oracle text (partial match). */
  oracleText?: string;
  /** Filter to cards legal in this format (e.g. 'modern', 'standard'). */
  legalIn?: string;
  /** Minimum converted mana cost (inclusive). */
  cmcMin?: number;
  /** Maximum converted mana cost (inclusive). */
  cmcMax?: number;
  /** Cards must contain all of these colors (W/U/B/R/G). */
  colors?: string[];
  /** Cards must have color identity matching all of these colors. */
  colorIdentity?: string[];
  /** Filter to mana-producing cards only. */
  manaProducer?: boolean;
  /** Zero-based page number. */
  page?: number;
  /** Number of results per page (max 100). */
  limit?: number;
}

export interface CardSearchResult {
  data: JsonApiResource<MtgCardAttributes>[];
  meta: {
    count: number;
    pages: number;
  };
}

// ---------------------------------------------------------------------------
// Request builder
// ---------------------------------------------------------------------------

function buildParams(params: CardSearchParams): Record<string, string | string[]> {
  const out: Record<string, string | string[]> = {};

  if (params.q) out['q'] = params.q;
  if (params.type) out['type'] = params.type;
  if (params.oracleText) out['oracle_text'] = params.oracleText;
  if (params.legalIn) out['legal_in'] = params.legalIn;
  if (params.cmcMin != null) out['cmc_min'] = String(params.cmcMin);
  if (params.cmcMax != null) out['cmc_max'] = String(params.cmcMax);
  if (params.colors && params.colors.length > 0) out['colors[]'] = params.colors;
  if (params.colorIdentity && params.colorIdentity.length > 0) out['color_identity[]'] = params.colorIdentity;
  if (params.manaProducer != null) out['mana_producer'] = params.manaProducer ? '1' : '0';
  if (params.page != null) out['page'] = String(params.page);
  if (params.limit != null) out['limit'] = String(params.limit);

  return out;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Searches MTG cards using the Solr-backed REST endpoint.
 */
export async function searchCards(params: CardSearchParams): Promise<CardSearchResult> {
  const response = await client.get<CardSearchResult>('/card-search', {
    params: buildParams(params),
  });
  return response.data;
}
