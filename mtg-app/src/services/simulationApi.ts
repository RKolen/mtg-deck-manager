/**
 * Client for POST /api/simulate and simulation history via GraphQL.
 */

import { gql } from 'graphql-request';
import { getGraphQLClient } from './graphqlClient';
import { createDrupalClient } from './httpClient';

const client = createDrupalClient('/api');

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SimulateRequest {
  playerDeckId: number;
  opponentArchetype: string;
  format?: string;
  games?: number;
  useLlm?: boolean;
  /** Advanced override for Forge single-pilot limit; UI omits this (auto from prompts). */
  pilotSide?: 'auto' | 'player' | 'opponent';
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

export interface MulliganStats {
  avgPlayerMulligan: number;
  avgOpponentMulligan: number;
  distribution: Record<string, number>;
  keepRate: number;
}

export interface TurnBreakdownRow {
  turn: number;
  avgCreatures: number;
  avgBoardPower: number;
  avgHandSize: number;
  avgDamageDealt: number;
}

export interface LifeProgressionRow {
  turn: number;
  avgPlayerLife: number;
  avgOppLife: number;
}

export interface TurnEvent {
  turn: number;
  player: number;           // 0 = simulated player, 1 = opponent
  manaAvailable: number;
  plays: string[];
  damageDealt: number;
  lifeTotals: [number, number];
  handSize: number;
  handCards?: string;
  creaturesInPlay: number;
  boardPower: number;
}

export interface GameLog {
  gameIndex: number;
  onThePlay: boolean;
  playerMulligan: number;
  opponentMulligan: number;
  playerOpeningHand: string[];
  winner: number;
  finalTurn: number;
  playerFinalLife: number;
  opponentFinalLife: number;
  winCondition: string;
  pilotNotes?: string[];
  playerPilotNotes?: string[];
  opponentPilotNotes?: string[];
  turns: TurnEvent[];
}

export interface PilotInfo {
  engineUsed: string;
  opponentPilotActive: boolean;
  playerPilotActive: boolean;
  opponentPilotSource: string;
  playerPilotSource: string;
  llmAvailable: boolean;
  opponentPromptChars: number;
  playerPromptChars: number;
  opponentPromptOriginalChars?: number;
  playerPromptOriginalChars?: number;
  opponentPromptPreview?: string;
  playerPromptPreview?: string;
  cavemanMode?: string;
  cavemanPlayerApplied?: boolean;
  cavemanOpponentApplied?: boolean;
  message: string;
}

export interface SimulationResult {
  playerDeck: string;
  opponentArchetype: string;
  format: string;
  engineUsed?: string;
  pilotInfo?: PilotInfo;
  games: number;
  wins: number;
  losses: number;
  winRate: number;
  onThePlay: HalfStats;
  onTheDraw: HalfStats;
  avgTurnWin: number | null;
  avgTurnLoss: number | null;
  topKillers: TopKiller[];
  keyMoments: string[];
  mulliganStats: MulliganStats;
  avgMulliganCount: number;
  manaEfficiency: number;
  lifeProgression: LifeProgressionRow[];
  turnBreakdown: TurnBreakdownRow[];
  winConditions: Record<string, number>;
  gameLogs: GameLog[];
}

export interface SimDeckCard {
  id: string;
  quantity: number;
  isSideboard: boolean;
  card: {
    id: string;
    title: string;
    manaCost: string | null;
    typeLine: string | null;
    imageUri: string | null;
  };
}

export interface SimulationHistoryEntry {
  id: string;
  nid: number;
  opponent: string;
  format: string;
  games: number;
  wins: number;
  winRate: number;
  resultJson: string;
  created: string;
  deckTitle: string;
  deckNotes: string | null;
  deckCards: SimDeckCard[];
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export async function runSimulation(req: SimulateRequest): Promise<SimulationResult> {
  const response = await client.post<SimulationResult>('/simulate', req, {
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    timeout: 660_000,
  });
  return response.data;
}

export async function fetchSimulationHistory(
  deckNid: number,
  limit = 20,
): Promise<SimulationHistoryEntry[]> {
  const query = gql`
    query GetSimHistory($deckNid: Int!, $limit: Int) {
      simulationHistory(deckNid: $deckNid, limit: $limit) {
        id nid opponent format games wins winRate resultJson created
        deckTitle deckNotes
        deckCards {
          id quantity isSideboard
          card { id title manaCost typeLine imageUri }
        }
      }
    }
  `;
  const data = await getGraphQLClient().request<{
    simulationHistory: SimulationHistoryEntry[];
  }>(query, { deckNid, limit });
  return data.simulationHistory;
}
