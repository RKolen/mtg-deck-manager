/**
 * Client for the interactive MTG game endpoints on the Python sim service.
 *
 * Calls http://localhost:8002/game/* directly (not through Drupal) so the
 * game state round-trips are as fast as possible.
 */
import axios from 'axios';

const SIM_URL = process.env.GATSBY_SIM_URL ?? 'http://localhost:8002';
const client = axios.create({ baseURL: SIM_URL, timeout: 30_000 });

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CardInHand {
  idx: number;
  name: string;
  cmc: number;
  type: string;
  power: number;
  toughness: number;
  oracle: string;
  category: 'land' | 'creature' | 'burn' | 'pump' | 'removal' | 'draw' | 'aura' | 'spell';
  isLand: boolean;
  isCreature: boolean;
  affordable: boolean;
}

export interface PermanentOnBoard {
  uid: string;
  name: string;
  cmc: number;
  type: string;
  power: number;
  toughness: number;
  tapped: boolean;
  sick: boolean;
  canAttack: boolean;
  oracle: string;
  counters: Record<string, number>;
}

export interface LogEntry {
  turn: number;
  actor: 'player' | 'opponent' | 'system';
  action: string;
  detail: string;
}

export interface GameState {
  gameId: string;
  turn: number;
  phase: string;
  winner: number | null;

  playerHand: CardInHand[];
  playerBattlefield: PermanentOnBoard[];
  playerLife: number;
  playerMana: number;
  playerTotalMana: number;
  playerLandPlayed: boolean;
  playerGraveyard: string[];

  opponentHandCount: number;
  opponentBattlefield: PermanentOnBoard[];
  opponentLife: number;
  opponentMana: number;
  opponentGraveyard: string[];

  log: LogEntry[];
  pendingAttackers: string[];
  availableActions: string[];
  error?: string;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export async function startGame(
  playerDeckId: number,
  opponentArchetype: string,
  format: string,
  onThePlay: boolean,
): Promise<GameState> {
  const r = await client.post<GameState>('/game/start', {
    playerDeckId, opponentArchetype, format, onThePlay,
  });
  return r.data;
}

export async function gameAction(
  gameId: string,
  action: string,
  opts: {
    handIdx?: number;
    targetUid?: string;
    targetPlayer?: number;
    permanentUid?: string;
  } = {},
): Promise<GameState> {
  const r = await client.post<GameState>('/game/action', {
    gameId, action, ...opts,
  });
  return r.data;
}

export async function getGameState(gameId: string): Promise<GameState> {
  const r = await client.get<GameState>(`/game/state/${gameId}`);
  return r.data;
}

export async function deleteGame(gameId: string): Promise<void> {
  await client.delete(`/game/${gameId}`);
}
