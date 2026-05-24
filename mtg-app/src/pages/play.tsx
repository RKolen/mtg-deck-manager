/**
 * Interactive MTG game page — play your deck against an AI archetype.
 *
 * Route: /play?deckId=<nid>&vs=<archetype>&format=<format>&play=1|0
 *
 * Navigate here from the deck editor's Simulate tab.
 * Game state lives in the Python sim service (http://localhost:8002).
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'gatsby';
import {
  startGame,
  gameAction,
  deleteGame,
  type GameState,
  type CardInHand,
  type PermanentOnBoard,
} from '../services/gameApi';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function useQueryParam(name: string): string | null {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get(name);
}

function oracleHas(oracle: string, keyword: string): boolean {
  return oracle.toLowerCase().includes(keyword.toLowerCase());
}

type PendingAlt =
  | 'bloodrush'
  | 'ninjutsu'
  | 'casualty'
  | 'boast'
  | 'outlast'
  | 'craft_host'
  | 'craft_artifacts'
  | null;

type PendingGyAction =
  | 'encore'
  | 'eternalize'
  | 'unearth'
  | 'cast_disturb'
  | 'cast_flashback'
  | null;

const PHASE_LABELS: Record<string, string> = {
  mulligan: 'Mulligan',
  draw: 'Draw step',
  main1: 'Main phase 1',
  attack: 'Combat',
  main2: 'Main phase 2',
  end: 'End step',
  opp_turn: 'Opponent\'s turn…',
  game_over: 'Game over',
};

const CATEGORY_COLORS: Record<string, string> = {
  land: '#8fbc8f',
  creature: '#4a90d9',
  burn: '#e74c3c',
  pump: '#2ecc71',
  removal: '#9b59b6',
  draw: '#3498db',
  aura: '#f39c12',
  spell: '#95a5a6',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const LifeBar: React.FC<{ label: string; life: number; mana?: number; handCount?: number }> = ({
  label, life, mana, handCount,
}) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0.4rem 0.75rem', background: '#222', color: '#eee', borderRadius: 4 }}>
    <span style={{ fontWeight: 700, fontSize: '0.85rem', minWidth: 90 }}>{label}</span>
    <span style={{ fontSize: '1.4rem', fontWeight: 800, color: life <= 5 ? '#e74c3c' : '#2ecc71', minWidth: 40 }}>{life}</span>
    {mana !== undefined && (
      <span style={{ color: '#f1c40f', fontSize: '0.8rem' }}>{mana} mana</span>
    )}
    {handCount !== undefined && (
      <span style={{ color: '#bbb', fontSize: '0.8rem' }}>{handCount} in hand</span>
    )}
  </div>
);

const CardChip: React.FC<{
  card: CardInHand;
  selected?: boolean;
  onClick?: () => void;
  dimmed?: boolean;
}> = ({ card, selected, onClick, dimmed }) => (
  <div
    onClick={onClick}
    title={card.oracle}
    style={{
      cursor: onClick ? 'pointer' : 'default',
      border: `2px solid ${selected ? '#f1c40f' : CATEGORY_COLORS[card.category] ?? '#555'}`,
      borderRadius: 6,
      padding: '0.35rem 0.6rem',
      background: selected ? '#3a3000' : dimmed ? '#1a1a1a' : '#2a2a2a',
      color: dimmed ? '#666' : '#eee',
      transition: 'border-color 0.15s',
      minWidth: 80,
      maxWidth: 160,
      fontSize: '0.78rem',
      userSelect: 'none',
    }}
  >
    <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{card.name}</div>
    <div style={{ color: '#aaa', fontSize: '0.72rem' }}>
      {card.isLand ? 'Land' : `${card.type} - ${card.cmc} CMC`}
      {card.isCreature && ` - ${card.power}/${card.toughness}`}
    </div>
  </div>
);

const BoardCard: React.FC<{
  perm: PermanentOnBoard;
  selected?: boolean;
  onClick?: () => void;
  dim?: boolean;
}> = ({ perm, selected, onClick, dim }) => (
  <div
    onClick={onClick}
    title={perm.oracle}
    style={{
      cursor: onClick ? 'pointer' : 'default',
      border: `2px solid ${selected ? '#f1c40f' : perm.tapped ? '#555' : '#4a90d9'}`,
      borderRadius: 6,
      padding: '0.35rem 0.55rem',
      background: perm.tapped ? '#1a1a1a' : dim ? '#1e1e1e' : '#252535',
      color: dim ? '#666' : '#eee',
      transform: perm.tapped ? 'rotate(10deg)' : 'none',
      transition: 'transform 0.15s',
      minWidth: 72,
      maxWidth: 130,
      fontSize: '0.75rem',
      userSelect: 'none',
      opacity: perm.sick ? 0.65 : 1,
    }}
  >
    <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{perm.name}</div>
    {perm.type === 'Creature' && (
      <div style={{ color: '#aaa', fontSize: '0.7rem' }}>{perm.power}/{perm.toughness}{perm.sick ? ' (sick)' : ''}</div>
    )}
    {selected && <div style={{ color: '#f1c40f', fontSize: '0.7rem' }}>attacking</div>}
  </div>
);

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const PlayPage: React.FC = () => {
  const deckId    = useQueryParam('deckId');
  const vsArch    = useQueryParam('vs');
  const format    = useQueryParam('format') ?? 'Modern';
  const playFirst = useQueryParam('play') !== '0';

  const [gs, setGs] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // UI state for casting / targeting
  const [selectedHandIdx, setSelectedHandIdx] = useState<number | null>(null);
  const [targetMode, setTargetMode] = useState<'none' | 'self' | 'opp'>('none');
  const [waitingTarget, setWaitingTarget] = useState(false);
  const [castForEvoke, setCastForEvoke] = useState(false);
  const [castForMiracle, setCastForMiracle] = useState(false);
  const [paidCasualty, setPaidCasualty] = useState(false);
  const [casualtySacrificeUid, setCasualtySacrificeUid] = useState<string | null>(null);
  const [pendingAlt, setPendingAlt] = useState<PendingAlt>(null);
  const [pendingGyAction, setPendingGyAction] = useState<PendingGyAction>(null);
  const [craftHostUid, setCraftHostUid] = useState<string | null>(null);
  const [craftArtifactIds, setCraftArtifactIds] = useState<string[]>([]);

  const logRef = useRef<HTMLDivElement>(null);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [gs?.log]);

  // Start the game on mount
  useEffect(() => {
    if (!deckId || !vsArch) return;
    setLoading(true);
    startGame(Number(deckId), vsArch, format, playFirst)
      .then(state => { setGs(state); setLoading(false); })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => { if (gs?.gameId) void deleteGame(gs.gameId); };
  }, [gs?.gameId]);

  const act = useCallback(async (action: string, opts: Record<string, unknown> = {}) => {
    if (!gs) return;
    setLoading(true);
    setSelectedHandIdx(null);
    setTargetMode('none');
    setWaitingTarget(false);
    setCastForEvoke(false);
    setCastForMiracle(false);
    setPaidCasualty(false);
    setCasualtySacrificeUid(null);
    setPendingAlt(null);
    setPendingGyAction(null);
    setCraftHostUid(null);
    setCraftArtifactIds([]);
    try {
      const next = await gameAction(gs.gameId, action, opts as Parameters<typeof gameAction>[2]);
      setGs(next);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [gs]);

  // ---- Derived state ----
  const phase = gs?.phase ?? '';
  const isDone = phase === 'game_over';
  const isOppTurn = phase === 'opp_turn';
  const isMulligan = phase === 'mulligan';
  const canPlayLand = gs?.availableActions.includes('play_land') && !gs.playerLandPlayed;
  const canCast = gs?.availableActions.includes('cast_spell');
  const canCycle = gs?.availableActions.includes('cycle');
  const canChannel = gs?.availableActions.includes('channel');
  const canBloodrush = gs?.availableActions.includes('bloodrush');
  const canNinjutsu = gs?.availableActions.includes('ninjutsu');
  const canBoast = gs?.availableActions.includes('boast');
  const canOutlast = gs?.availableActions.includes('outlast');
  const canCraft = gs?.availableActions.includes('craft');
  const canEncore = gs?.availableActions.includes('encore');
  const canEternalize = gs?.availableActions.includes('eternalize');
  const canUnearth = gs?.availableActions.includes('unearth');
  const canDisturb = gs?.availableActions.includes('cast_disturb');
  const canFlashback = gs?.availableActions.includes('cast_flashback');
  const _canAttack = gs?.availableActions.includes('go_to_attack') || phase === 'attack'; void _canAttack;
  const inCombat = phase === 'attack';

  const selectedCard = selectedHandIdx !== null ? gs?.playerHand[selectedHandIdx] : null;

  // ---- Handlers ----

  function handleHandClick(card: CardInHand, idx: number) {
    if (!(canPlayLand && card.isLand) && !card.affordable) return;
    if (card.isLand && canPlayLand) {
      void act('play_land', { handIdx: idx });
      return;
    }
    if (!canCast) return;
    if (selectedHandIdx === idx) {
      setSelectedHandIdx(null);
      setTargetMode('none');
      setWaitingTarget(false);
      setCastForEvoke(false);
      setCastForMiracle(false);
      setPaidCasualty(false);
      setCasualtySacrificeUid(null);
      setPendingAlt(null);
      setPendingGyAction(null);
      return;
    }
    setSelectedHandIdx(idx);
    setCastForEvoke(false);
    setCastForMiracle(false);
    setPaidCasualty(false);
    setCasualtySacrificeUid(null);
    setPendingAlt(null);
    setPendingGyAction(null);
    if (['burn', 'pump', 'removal'].includes(card.category)) {
      setWaitingTarget(true);
      setTargetMode(card.category === 'pump' ? 'self' : 'opp');
    } else if (
      oracleHas(card.oracle, 'Miracle')
      || oracleHas(card.oracle, 'Casualty')
      || card.hasEvoke
    ) {
      // Wait for Cast / options before sending to server
    } else {
      void act('cast', { handIdx: idx, targetPlayer: 1, castForEvoke: false });
    }
  }

  function startBloodrush(idx: number) {
    setSelectedHandIdx(idx);
    setPendingAlt('bloodrush');
    setWaitingTarget(true);
    setTargetMode('self');
  }

  function startNinjutsu(idx: number) {
    setSelectedHandIdx(idx);
    setPendingAlt('ninjutsu');
    setWaitingTarget(true);
    setTargetMode('self');
  }

  function castSelected(opts: { targetUid?: string; targetPlayer?: number }) {
    if (selectedHandIdx === null) return;
    if (paidCasualty && !casualtySacrificeUid) {
      setPendingAlt('casualty');
      setWaitingTarget(true);
      setTargetMode('self');
      return;
    }
    void act('cast', {
      handIdx: selectedHandIdx,
      targetUid: opts.targetUid,
      targetPlayer: opts.targetPlayer ?? 1,
      castForEvoke,
      castForMiracle,
      paidCasualty,
      casualtySacrificeIds: casualtySacrificeUid ? [casualtySacrificeUid] : [],
    });
  }

  function handlePlayerBoardClick(perm: PermanentOnBoard) {
    if (pendingAlt === 'bloodrush') {
      if (selectedHandIdx === null) return;
      void act('bloodrush', { handIdx: selectedHandIdx, targetUid: perm.uid });
      return;
    }
    if (pendingAlt === 'ninjutsu') {
      if (selectedHandIdx === null) return;
      void act('ninjutsu', { handIdx: selectedHandIdx, targetUid: perm.uid });
      return;
    }
    if (pendingAlt === 'casualty') {
      setCasualtySacrificeUid(perm.uid);
      setPendingAlt(null);
      setWaitingTarget(false);
      setTargetMode('none');
      return;
    }
    if (pendingAlt === 'boast') {
      void act('boast', { permanentUid: perm.uid });
      return;
    }
    if (pendingAlt === 'outlast') {
      void act('outlast', { permanentUid: perm.uid });
      return;
    }
    if (pendingAlt === 'craft_host') {
      if (!oracleHas(perm.oracle, 'Craft')) return;
      setCraftHostUid(perm.uid);
      setCraftArtifactIds([]);
      setPendingAlt('craft_artifacts');
      return;
    }
    if (pendingAlt === 'craft_artifacts') {
      if (!perm.type.includes('Artifact')) return;
      setCraftArtifactIds(prev =>
        prev.includes(perm.uid) ? prev.filter(id => id !== perm.uid) : [...prev, perm.uid],
      );
      return;
    }
    if (waitingTarget && targetMode === 'self') {
      handleTargetPermanent(perm, false);
    } else if (inCombat && perm.canAttack) {
      void act('toggle_attacker', { permanentUid: perm.uid });
    }
  }

  function confirmCraft() {
    if (!craftHostUid || craftArtifactIds.length === 0) return;
    void act('craft', { permanentUid: craftHostUid, craftArtifactIds });
  }

  function handleGraveyardClick(idx: number) {
    if (!pendingGyAction) return;
    void act(pendingGyAction, { handIdx: idx, targetPlayer: 1 });
  }

  function handleTargetPermanent(perm: PermanentOnBoard, isOppBoard: boolean) {
    if (!waitingTarget || selectedHandIdx === null) return;
    if (pendingAlt === 'bloodrush' && !isOppBoard) {
      void act('bloodrush', { handIdx: selectedHandIdx, targetUid: perm.uid });
      return;
    }
    if (pendingAlt === 'ninjutsu' && !isOppBoard) {
      void act('ninjutsu', { handIdx: selectedHandIdx, targetUid: perm.uid });
      return;
    }
    if (pendingAlt === 'casualty' && !isOppBoard) {
      setCasualtySacrificeUid(perm.uid);
      setPendingAlt(null);
      setWaitingTarget(false);
      setTargetMode('none');
      return;
    }
    castSelected({
      targetUid: perm.uid,
      targetPlayer: isOppBoard ? 1 : 0,
    });
  }

  function resetPendingUi() {
    setSelectedHandIdx(null);
    setTargetMode('none');
    setWaitingTarget(false);
    setCastForEvoke(false);
    setCastForMiracle(false);
    setPaidCasualty(false);
    setCasualtySacrificeUid(null);
    setPendingAlt(null);
    setPendingGyAction(null);
    setCraftHostUid(null);
    setCraftArtifactIds([]);
  }

  function handleTargetOpponent() {
    if (!waitingTarget || selectedHandIdx === null || pendingAlt) return;
    castSelected({ targetPlayer: 1 });
  }

  // ---- Render ----

  if (!deckId || !vsArch) {
    return (
      <main style={{ padding: '2rem', color: '#eee', background: '#111', minHeight: '100vh' }}>
        <h2>Missing parameters</h2>
        <p>Navigate here from the deck editor's Simulate tab.</p>
        <Link to="/" style={{ color: '#4a90d9' }}>Back to home</Link>
      </main>
    );
  }

  if (error) {
    return (
      <main style={{ padding: '2rem', color: '#eee', background: '#111', minHeight: '100vh' }}>
        <h2 style={{ color: '#e74c3c' }}>Error</h2>
        <pre style={{ color: '#aaa' }}>{error}</pre>
        <p style={{ color: '#888' }}>Make sure the sim service is running: <code>cd mtg-sim/sim && python main.py</code></p>
        <Link to="/" style={{ color: '#4a90d9' }}>Back to home</Link>
      </main>
    );
  }

  if (!gs || loading && !gs) {
    return (
      <main style={{ padding: '2rem', color: '#eee', background: '#111', minHeight: '100vh' }}>
        <p>Starting game…</p>
      </main>
    );
  }

  return (
    <main style={{ background: '#111', minHeight: '100vh', color: '#eee', display: 'flex', flexDirection: 'column' }}>

      {/* Header bar */}
      <div style={{ background: '#1a1a2e', padding: '0.5rem 1rem', display: 'flex', alignItems: 'center', gap: 16, borderBottom: '1px solid #333' }}>
        <Link to={`/decks/${vsArch}`} style={{ color: '#aaa', fontSize: '0.85rem' }}>Back</Link>
        <span style={{ fontWeight: 700, fontSize: '1rem' }}>You vs {vsArch}</span>
        <span style={{ color: '#f1c40f', fontSize: '0.9rem', fontWeight: 600 }}>
          T{gs.turn} — {PHASE_LABELS[phase] ?? phase}
        </span>
        {loading && <span style={{ color: '#888', fontSize: '0.85rem' }}>Processing...</span>}
        {gs.error && <span style={{ color: '#e74c3c', fontSize: '0.85rem' }}>Error: {gs.error}</span>}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {isDone && (
            <button type="button"
              style={{ background: '#4a90d9', color: '#fff', border: 'none', borderRadius: 4, padding: '0.3rem 0.8rem', cursor: 'pointer' }}
              onClick={() => {
                void deleteGame(gs.gameId);
                startGame(Number(deckId), vsArch, format, playFirst).then(setGs);
              }}
            >New game</button>
          )}
        </div>
      </div>

      {/* Game board — 3 rows: opponent, info strip, player */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '0.75rem', gap: '0.75rem' }}>

        {/* Opponent side */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: '0 0 auto' }}>
          <LifeBar label={vsArch} life={gs.opponentLife} mana={gs.opponentMana} handCount={gs.opponentHandCount} />

          {/* Opponent's hidden hand */}
          {gs.opponentHandCount > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {Array.from({ length: gs.opponentHandCount }).map((_, i) => (
                <div key={i} style={{ width: 48, height: 64, background: '#2a2a4a', border: '1px solid #444', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#666', fontSize: '0.7rem' }}>Card</div>
              ))}
            </div>
          )}

          {/* Opponent battlefield */}
          <div style={{ minHeight: 80, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'flex-start' }}>
            {gs.opponentBattlefield.length === 0 ? (
              <span style={{ color: '#444', fontSize: '0.8rem', alignSelf: 'center' }}>Empty battlefield</span>
            ) : gs.opponentBattlefield.map(p => (
              <BoardCard
                key={p.uid}
                perm={p}
                dim={waitingTarget && targetMode !== 'opp'}
                onClick={waitingTarget && targetMode === 'opp' ? () => handleTargetPermanent(p, true) : undefined}
              />
            ))}
            {/* "Target opponent player" button when in burn mode */}
            {waitingTarget && targetMode === 'opp' && (
              <button type="button"
                onClick={handleTargetOpponent}
                style={{ alignSelf: 'center', background: '#e74c3c', color: '#fff', border: 'none', borderRadius: 4, padding: '0.3rem 0.6rem', cursor: 'pointer', fontSize: '0.8rem' }}
              >
                Hit opponent directly
              </button>
            )}
          </div>
        </div>

        {/* Divider / phase info */}
        <div style={{ borderTop: '1px solid #333', borderBottom: '1px solid #333', padding: '0.4rem 0', display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Graveyard info */}
          <span style={{ color: '#666', fontSize: '0.78rem' }}>
            Opp GY: {gs.opponentGraveyard.slice(-3).join(', ') || '—'}
          </span>
          <span style={{ color: '#444' }}>|</span>
          <span style={{ color: '#666', fontSize: '0.78rem' }}>
            Your GY: {gs.playerGraveyard.slice(-3).join(', ') || '—'}
          </span>
          {(pendingAlt || pendingGyAction) && (
            <span style={{ marginLeft: 'auto', color: '#f1c40f', fontWeight: 600, fontSize: '0.85rem' }}>
              {pendingAlt === 'bloodrush' && 'Bloodrush: click your creature to pump'}
              {pendingAlt === 'ninjutsu' && 'Ninjutsu: click your attacker to replace'}
              {pendingAlt === 'casualty' && 'Casualty: click a creature to sacrifice'}
              {pendingAlt === 'boast' && 'Boast: click an attacking creature'}
              {pendingAlt === 'outlast' && 'Outlast: click a creature with outlast'}
              {pendingAlt === 'craft_host' && 'Craft: click the permanent to craft'}
              {pendingAlt === 'craft_artifacts' && 'Craft: click artifacts to exile, then confirm'}
              {pendingGyAction === 'encore' && 'Encore: click a creature in your graveyard'}
              {pendingGyAction === 'eternalize' && 'Eternalize: click a creature in your graveyard'}
              {pendingGyAction === 'unearth' && 'Unearth: click a card in your graveyard'}
              {pendingGyAction === 'cast_disturb' && 'Disturb: click a creature in your graveyard'}
              {pendingGyAction === 'cast_flashback' && 'Flashback: click a card in your graveyard'}
            </span>
          )}
          {selectedCard && waitingTarget && !pendingAlt && !pendingGyAction && (
            <span style={{ marginLeft: 'auto', color: '#f1c40f', fontWeight: 600, fontSize: '0.85rem' }}>
              {targetMode === 'opp'
                ? 'Click a target on the opponent side'
                : 'Click one of your creatures'}
            </span>
          )}
          {selectedCard && !waitingTarget && (
            <span style={{ marginLeft: 'auto', color: '#aaa', fontSize: '0.85rem' }}>
              Selected: {selectedCard.name}
            </span>
          )}
        </div>

        {/* Player battlefield */}
        <div style={{ minHeight: 90, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          {gs.playerBattlefield.length === 0 ? (
            <span style={{ color: '#444', fontSize: '0.8rem', alignSelf: 'center' }}>Your battlefield is empty</span>
          ) : gs.playerBattlefield.map(p => (
            <BoardCard
              key={p.uid}
              perm={p}
              selected={
                gs.pendingAttackers.includes(p.uid)
                || craftArtifactIds.includes(p.uid)
                || craftHostUid === p.uid
              }
              onClick={
                pendingAlt || (waitingTarget && targetMode === 'self') || (inCombat && p.canAttack)
                  ? () => handlePlayerBoardClick(p)
                  : undefined
              }
            />
          ))}
        </div>

        {(gs.playerGraveyardCards?.length ?? 0) > 0 && pendingGyAction && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ color: '#888', fontSize: '0.78rem' }}>Graveyard:</span>
            {gs.playerGraveyardCards!.map(card => (
              <button
                key={card.idx}
                type="button"
                onClick={() => handleGraveyardClick(card.idx)}
                style={btnStyle('#34495e')}
              >
                [{card.idx}] {card.name}
              </button>
            ))}
          </div>
        )}

        {/* Player life + mana */}
        <LifeBar label="You" life={gs.playerLife} mana={gs.playerMana} />

        {/* Action buttons */}
        {!isDone && !isOppTurn && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {isMulligan && <>
              <button type="button" onClick={() => void act('keep')} style={btnStyle('#27ae60')}>
                Keep hand ({gs.playerHand.length} cards)
              </button>
              <button type="button" onClick={() => void act('mulligan')} disabled={gs.playerHand.length <= 4} style={btnStyle('#e67e22')}>
                Mulligan to {gs.playerHand.length - 1}
              </button>
            </>}

            {phase === 'draw' && (
              <button type="button" onClick={() => void act('draw')} style={btnStyle('#4a90d9')}>
                Draw card
              </button>
            )}

            {phase === 'main1' && <>
              {!waitingTarget && (
                <button type="button" onClick={() => void act('go_to_attack')} style={btnStyle('#e67e22')}>
                  Go to combat
                </button>
              )}
              <button type="button" onClick={() => void act('end_turn')} style={btnStyle('#555')}>
                End turn
              </button>
            </>}

            {inCombat && <>
              <button type="button" onClick={() => void act('confirm_attack')} style={btnStyle('#e74c3c')} disabled={gs.pendingAttackers.length === 0}>
                Attack ({gs.pendingAttackers.length} creatures)
              </button>
              <button type="button" onClick={() => void act('skip_attack')} style={btnStyle('#555')}>
                Skip combat
              </button>
            </>}

            {phase === 'main2' && (
              <button type="button" onClick={() => void act('end_turn')} style={btnStyle('#555')}>
                End turn
              </button>
            )}

            {selectedCard && !isMulligan && (
              <>
                {selectedCard.hasEvoke && canCast && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={castForEvoke}
                      disabled={!selectedCard.evokeAffordable}
                      onChange={e => setCastForEvoke(e.target.checked)}
                    />
                    Cast for Evoke
                  </label>
                )}
                {canCast && oracleHas(selectedCard.oracle, 'Miracle') && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={castForMiracle}
                      onChange={e => setCastForMiracle(e.target.checked)}
                    />
                    Cast for Miracle
                  </label>
                )}
                {canCast && oracleHas(selectedCard.oracle, 'Casualty') && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={paidCasualty}
                      onChange={e => {
                        setPaidCasualty(e.target.checked);
                        if (!e.target.checked) setCasualtySacrificeUid(null);
                      }}
                    />
                    Pay Casualty
                    {casualtySacrificeUid && ' (sacrifice selected)'}
                  </label>
                )}
                {canCast && !waitingTarget && !selectedCard.isLand && (
                  <button
                    type="button"
                    disabled={!selectedCard.affordable}
                    onClick={() => castSelected({ targetPlayer: 1 })}
                    style={btnStyle('#2980b9')}
                  >
                    Cast {selectedCard.name}
                  </button>
                )}
                {selectedCard.canBloodrush && canBloodrush && (
                  <button
                    type="button"
                    disabled={!selectedCard.bloodrushAffordable}
                    onClick={() => startBloodrush(selectedHandIdx!)}
                    style={btnStyle('#9b59b6')}
                  >
                    Bloodrush
                  </button>
                )}
                {selectedCard.canNinjutsu && canNinjutsu && (
                  <button
                    type="button"
                    disabled={!selectedCard.ninjutsuAffordable}
                    onClick={() => startNinjutsu(selectedHandIdx!)}
                    style={btnStyle('#8e44ad')}
                  >
                    Ninjutsu
                  </button>
                )}
                {selectedCard.canCycle && canCycle && (
                  <button
                    type="button"
                    onClick={() => void act('cycle', { handIdx: selectedHandIdx! })}
                    style={btnStyle('#7f8c8d')}
                  >
                    Cycle
                  </button>
                )}
                {selectedCard.canChannel && canChannel && (
                  <button
                    type="button"
                    onClick={() => void act('channel', { handIdx: selectedHandIdx!, targetPlayer: 1 })}
                    style={btnStyle('#16a085')}
                  >
                    Channel
                  </button>
                )}
              </>
            )}

            {!selectedCard && !waitingTarget && !pendingAlt && !pendingGyAction && (
              <>
                {canBoast && (
                  <button type="button" onClick={() => setPendingAlt('boast')} style={btnStyle('#d35400')}>
                    Boast
                  </button>
                )}
                {canOutlast && (
                  <button type="button" onClick={() => setPendingAlt('outlast')} style={btnStyle('#e67e22')}>
                    Outlast
                  </button>
                )}
                {canCraft && (
                  <button type="button" onClick={() => setPendingAlt('craft_host')} style={btnStyle('#1abc9c')}>
                    Craft
                  </button>
                )}
                {canEncore && (
                  <button type="button" onClick={() => setPendingGyAction('encore')} style={btnStyle('#8e44ad')}>
                    Encore
                  </button>
                )}
                {canEternalize && (
                  <button type="button" onClick={() => setPendingGyAction('eternalize')} style={btnStyle('#6c3483')}>
                    Eternalize
                  </button>
                )}
                {canUnearth && (
                  <button type="button" onClick={() => setPendingGyAction('unearth')} style={btnStyle('#566573')}>
                    Unearth
                  </button>
                )}
                {canDisturb && (
                  <button type="button" onClick={() => setPendingGyAction('cast_disturb')} style={btnStyle('#5dade2')}>
                    Disturb
                  </button>
                )}
                {canFlashback && (
                  <button type="button" onClick={() => setPendingGyAction('cast_flashback')} style={btnStyle('#2874a6')}>
                    Flashback
                  </button>
                )}
              </>
            )}

            {pendingAlt === 'craft_artifacts' && (
              <button
                type="button"
                disabled={!craftHostUid || craftArtifactIds.length === 0}
                onClick={confirmCraft}
                style={btnStyle('#16a085')}
              >
                Confirm craft ({craftArtifactIds.length} artifacts)
              </button>
            )}

            {(waitingTarget || pendingAlt || pendingGyAction) && (
              <button
                type="button"
                onClick={resetPendingUi}
                style={btnStyle('#555')}
              >
                Cancel
              </button>
            )}
          </div>
        )}

        {isOppTurn && (
          <p style={{ color: '#888', fontStyle: 'italic', margin: 0 }}>Opponent is playing…</p>
        )}

        {isDone && (
          <div style={{ padding: '1rem', background: gs.winner === 0 ? '#1a3a1a' : '#3a1a1a', borderRadius: 6, textAlign: 'center' }}>
            <h2 style={{ color: gs.winner === 0 ? '#2ecc71' : '#e74c3c', margin: '0 0 0.5rem' }}>
              {gs.winner === 0 ? 'You win!' : 'You lose'}
            </h2>
            <p style={{ color: '#aaa', margin: 0 }}>Game ended on turn {gs.turn}</p>
          </div>
        )}

        {/* Player hand */}
        <div style={{ marginTop: 'auto' }}>
          <div style={{ color: '#888', fontSize: '0.78rem', marginBottom: 4 }}>
            Your hand ({gs.playerHand.length}) — {isMulligan ? 'Preview' : 'Click to play'}
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {gs.playerHand.map((card, idx) => {
              const isSelectable = (canPlayLand && card.isLand) || (!card.isLand && card.affordable);
              return (
                <CardChip
                  key={`${card.name}-${idx}`}
                  card={card}
                  selected={selectedHandIdx === idx}
                  dimmed={!isMulligan && !isSelectable}
                  onClick={!isMulligan && isSelectable ? () => handleHandClick(card, idx) : undefined}
                />
              );
            })}
          </div>
        </div>

      </div>

      {/* Log sidebar — floating on the right */}
      <div style={{
        position: 'fixed', right: 0, top: 0, bottom: 0,
        width: 260, background: '#161620', borderLeft: '1px solid #2a2a3a',
        display: 'flex', flexDirection: 'column', fontSize: '0.75rem',
      }}>
        <div style={{ padding: '0.4rem 0.6rem', borderBottom: '1px solid #2a2a3a', color: '#888', fontWeight: 600 }}>
          Game log
        </div>
        <div ref={logRef} style={{ flex: 1, overflow: 'auto', padding: '0.4rem 0.6rem' }}>
          {gs.log.map((entry, i) => {
            const color = entry.actor === 'player' ? '#4a90d9' : entry.actor === 'opponent' ? '#e74c3c' : '#f1c40f';
            return (
              <div key={i} style={{ marginBottom: 4, borderLeft: `3px solid ${color}`, paddingLeft: 6 }}>
                <span style={{ color: '#666', marginRight: 4 }}>T{entry.turn}</span>
                <span style={{ color, fontWeight: 600 }}>{entry.action}</span>
                {entry.detail && <div style={{ color: '#aaa', marginTop: 1 }}>{entry.detail}</div>}
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
};

function btnStyle(bg: string): React.CSSProperties {
  return {
    background: bg, color: '#fff', border: 'none', borderRadius: 4,
    padding: '0.35rem 0.85rem', cursor: 'pointer', fontWeight: 600,
    fontSize: '0.85rem', transition: 'opacity 0.15s',
  };
}

export default PlayPage;
