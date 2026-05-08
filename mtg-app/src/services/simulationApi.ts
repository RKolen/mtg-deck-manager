/**
 * Client for POST /api/simulate — MTG game simulation service (Phase 10B).
 *
 * Drupal proxies the request to the Python mtg-sim service and persists
 * the result as a simulation_result node.
 */

import { createDrupalClient } from './httpClient';

const client = createDrupalClient('/api');

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SimulateRequest {
  playerDeckId: number;
  opponentArchetype: string;
  format?: string;
  /** Number of games to run, 1–200 (default 50). */
  games?: number;
  /** Use Ollama for MCTS board evaluation — significantly slower. */
  useLlm?: boolean;
}

export interface HalfStats {
  wins: number;
  games: number;
  winRate: number;
}

export interface TopKiller {
  card: string;
  appearances: number;
  lossContribution: number;
}

export interface SimulationResult {
  playerDeck: string;
  opponentArchetype: string;
  format: string;
  games: number;
  wins: number;
  losses: number;
  winRate: number;
  onThePlay: HalfStats;
  onTheDraw: HalfStats;
  avgTurnWin: number;
  avgTurnLoss: number;
  topKillers: TopKiller[];
  keyMoments: string[];
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

/**
 * Runs a simulation and returns aggregate statistics.
 * Can take several minutes for 200 games with MCTS enabled.
 */
export async function runSimulation(req: SimulateRequest): Promise<SimulationResult> {
  const response = await client.post<SimulationResult>('/simulate', req, {
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    timeout: 660_000, // 11 min — matches Drupal's 600 s proxy timeout + buffer
  });
  return response.data;
}
