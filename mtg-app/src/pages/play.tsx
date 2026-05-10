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
    <span style={{ color: '#aaa', fontSize: '0.8rem' }}>♥</span>
    {mana !== undefined && (
      <span style={{ color: '#f1c40f', fontSize: '0.8rem' }}>⬡ {mana} mana</span>
    )}
    {handCount !== undefined && (
      <span style={{ color: '#bbb', fontSize: '0.8rem' }}>🃏 {handCount} cards</span>
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
      {card.isLand ? 'Land' : `${card.type} · ${card.cmc}◆`}
      {card.isCreature && ` · ${card.power}/${card.toughness}`}
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
    {selected && <div style={{ color: '#f1c40f', fontSize: '0.7rem' }}>⚔ attacking</div>}
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
  const _canAttack = gs?.availableActions.includes('go_to_attack') || phase === 'attack'; void _canAttack;
  const inCombat = phase === 'attack';

  const selectedCard = selectedHandIdx !== null ? gs?.playerHand[selectedHandIdx] : null;

  // ---- Handlers ----

  function handleHandClick(card: CardInHand, idx: number) {
    if (!canCast && !(canPlayLand && card.isLand)) return;
    if (card.isLand && canPlayLand) {
      void act('play_land', { handIdx: idx });
      return;
    }
    if (!canCast) return;
    if (selectedHandIdx === idx) {
      // Deselect
      setSelectedHandIdx(null);
      setTargetMode('none');
      setWaitingTarget(false);
      return;
    }
    setSelectedHandIdx(idx);
    // Determine if spell needs a target
    if (['burn', 'pump', 'removal'].includes(card.category)) {
      setWaitingTarget(true);
      setTargetMode(card.category === 'pump' ? 'self' : 'opp');
    } else {
      // No target needed — cast immediately
      void act('cast', { handIdx: idx, targetPlayer: 1 });
    }
  }

  function handleTargetPermanent(perm: PermanentOnBoard, isOppBoard: boolean) {
    if (!waitingTarget || selectedHandIdx === null) return;
    void act('cast', {
      handIdx: selectedHandIdx,
      targetUid: perm.uid,
      targetPlayer: isOppBoard ? 1 : 0,
    });
  }

  function handleTargetOpponent() {
    if (!waitingTarget || selectedHandIdx === null) return;
    void act('cast', { handIdx: selectedHandIdx, targetPlayer: 1 });
  }

  // ---- Render ----

  if (!deckId || !vsArch) {
    return (
      <main style={{ padding: '2rem', color: '#eee', background: '#111', minHeight: '100vh' }}>
        <h2>Missing parameters</h2>
        <p>Navigate here from the deck editor's Simulate tab.</p>
        <Link to="/" style={{ color: '#4a90d9' }}>← Home</Link>
      </main>
    );
  }

  if (error) {
    return (
      <main style={{ padding: '2rem', color: '#eee', background: '#111', minHeight: '100vh' }}>
        <h2 style={{ color: '#e74c3c' }}>Error</h2>
        <pre style={{ color: '#aaa' }}>{error}</pre>
        <p style={{ color: '#888' }}>Make sure the sim service is running: <code>cd mtg-sim/sim && python main.py</code></p>
        <Link to="/" style={{ color: '#4a90d9' }}>← Home</Link>
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
        <Link to={`/decks/${vsArch}`} style={{ color: '#aaa', fontSize: '0.85rem' }}>← Back</Link>
        <span style={{ fontWeight: 700, fontSize: '1rem' }}>You vs {vsArch}</span>
        <span style={{ color: '#f1c40f', fontSize: '0.9rem', fontWeight: 600 }}>
          T{gs.turn} — {PHASE_LABELS[phase] ?? phase}
        </span>
        {loading && <span style={{ color: '#888', fontSize: '0.85rem' }}>⏳ processing…</span>}
        {gs.error && <span style={{ color: '#e74c3c', fontSize: '0.85rem' }}>⚠ {gs.error}</span>}
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
                <div key={i} style={{ width: 48, height: 64, background: '#2a2a4a', border: '1px solid #444', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#444', fontSize: '1.2rem' }}>🂠</div>
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
                ⚡ Hit opponent directly
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
          {selectedCard && waitingTarget && (
            <span style={{ marginLeft: 'auto', color: '#f1c40f', fontWeight: 600, fontSize: '0.85rem' }}>
              {targetMode === 'opp' ? '⚡ Click a target on the opponent side' : '💚 Click one of your creatures'}
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
              selected={gs.pendingAttackers.includes(p.uid)}
              onClick={
                inCombat && p.canAttack
                  ? () => void act('toggle_attacker', { permanentUid: p.uid })
                  : waitingTarget && targetMode === 'self'
                  ? () => handleTargetPermanent(p, false)
                  : undefined
              }
            />
          ))}
        </div>

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
                Mulligan → {gs.playerHand.length - 1}
              </button>
            </>}

            {phase === 'draw' && (
              <button type="button" onClick={() => void act('draw')} style={btnStyle('#4a90d9')}>
                Draw card
              </button>
            )}

            {phase === 'main1' && <>
              {!canPlayLand && !waitingTarget && (
                <button type="button" onClick={() => void act('go_to_attack')} style={btnStyle('#e67e22')}>
                  ⚔ Go to combat
                </button>
              )}
              <button type="button" onClick={() => void act('end_turn')} style={btnStyle('#555')}>
                End turn →
              </button>
            </>}

            {inCombat && <>
              <button type="button" onClick={() => void act('confirm_attack')} style={btnStyle('#e74c3c')} disabled={gs.pendingAttackers.length === 0}>
                ⚔ Attack ({gs.pendingAttackers.length} creatures)
              </button>
              <button type="button" onClick={() => void act('skip_attack')} style={btnStyle('#555')}>
                Skip combat
              </button>
            </>}

            {phase === 'main2' && (
              <button type="button" onClick={() => void act('end_turn')} style={btnStyle('#555')}>
                End turn →
              </button>
            )}

            {waitingTarget && (
              <button type="button" onClick={() => { setWaitingTarget(false); setSelectedHandIdx(null); setTargetMode('none'); }} style={btnStyle('#555')}>
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
              {gs.winner === 0 ? '🏆 You Win!' : '💀 You Lose'}
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
              const isSelectable = (canPlayLand && card.isLand) || (canCast && !card.isLand);
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
