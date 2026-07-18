/**
 * Interactive MTG game page — play your deck against an AI archetype.
 *
 * Route: /play?deckId=<nid>&vs=<archetype>&format=<format>&play=1|0
 *
 * Navigate here from the deck editor's Simulate tab.
 * Game state lives in the Python sim service (NEXT_PUBLIC_SIM_URL).
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import axios from 'axios';
import {
  startGame,
  gameAction,
  deleteGame,
  type GameState,
  type CardInHand,
  type PermanentOnBoard,
  type LibraryCardSummary,
} from '../services/gameApi';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function oracleHas(oracle: string, keyword: string): boolean {
  return oracle.toLowerCase().includes(keyword.toLowerCase());
}

function scriptedModalLabels(oracle: string, count: number): string[] {
  const bullets = oracle
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('•') || line.startsWith('-'));
  if (bullets.length >= count) {
    return bullets.slice(0, count).map((line) => line.replace(/^[\s•-]+/, '').trim());
  }
  return Array.from({ length: count }, (_, index) => `Mode ${index + 1}`);
}

function modalNeedsTarget(label: string): boolean {
  const lower = label.toLowerCase();
  return (
    lower.includes('target')
    || lower.includes('destroy')
    || lower.includes('exile')
    || lower.includes('damage')
  );
}

function modalTargetMode(label: string): 'self' | 'opp' {
  const lower = label.toLowerCase();
  if (
    lower.includes('target creature')
    && !lower.includes('target opponent')
    && (lower.includes('-/-') || lower.includes('gets '))
  ) {
    return 'self';
  }
  return 'opp';
}

type PendingAlt =
  | 'bloodrush'
  | 'ninjutsu'
  | 'casualty'
  | 'bargain'
  | 'boast'
  | 'outlast'
  | 'craft_host'
  | 'craft_artifacts'
  | 'scavenge_target'
  | 'jump_discard'
  | 'retrace_discard'
  | null;

type PendingGyAction =
  | 'encore'
  | 'eternalize'
  | 'unearth'
  | 'cast_disturb'
  | 'cast_flashback'
  | 'cast_escape'
  | 'cast_jump_start'
  | 'cast_retrace'
  | 'cast_aftermath'
  | 'cast_harmonize'
  | 'dredge'
  | 'scavenge'
  | null;

type PendingExileAction = 'cast_foretell' | 'cast_plot' | null;

type PendingCastModifier =
  | 'convoke'
  | 'delve'
  | 'improvise'
  | 'emerge'
  | 'harmonize'
  | 'sneak'
  | null;

type PendingBoardAction = 'turn_up_morph' | null;

const PHASE_LABELS: Record<string, string> = {
  mulligan: 'Mulligan',
  draw: 'Draw step',
  main1: 'Main phase 1',
  attack: 'Combat',
  declare_blockers: 'Declare blockers',
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

function isFetchland(perm: PermanentOnBoard): boolean {
  return perm.type.includes('Land')
    && /search your library/i.test(perm.oracle)
    && /sacrifice/i.test(perm.oracle);
}

function actionErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    return err.message;
  }
  return String(err);
}

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
  statusLabel?: string;
}> = ({ perm, selected, onClick, dim, statusLabel }) => (
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
    {statusLabel && <div style={{ color: '#2ecc71', fontSize: '0.7rem' }}>{statusLabel}</div>}
    {selected && !statusLabel && <div style={{ color: '#f1c40f', fontSize: '0.7rem' }}>attacking</div>}
  </div>
);

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const PlayPage: React.FC = () => {
  const router = useRouter();
  const deckId = typeof router.query.deckId === 'string' ? router.query.deckId : null;
  const vsArch = typeof router.query.vs === 'string' ? router.query.vs : null;
  const format = typeof router.query.format === 'string' ? router.query.format : 'Modern';
  const playFirst = router.query.play !== '0';

  const [gs, setGs] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedBlockerUid, setSelectedBlockerUid] = useState<string | null>(null);
  const [pendingLandPlay, setPendingLandPlay] = useState<number | null>(null);
  const [pendingFetchChoice, setPendingFetchChoice] = useState<LibraryCardSummary | null>(null);
  const actionInFlightRef = useRef(false);

  const busy = loading;
  const [selectedHandIdx, setSelectedHandIdx] = useState<number | null>(null);
  const [targetMode, setTargetMode] = useState<'none' | 'self' | 'opp'>('none');
  const [waitingTarget, setWaitingTarget] = useState(false);
  const [castForEvoke, setCastForEvoke] = useState(false);
  const [castForEmerge, setCastForEmerge] = useState(false);
  const [castForSpectacle, setCastForSpectacle] = useState(false);
  const [castForMorph, setCastForMorph] = useState(false);
  const [castForDisguise, setCastForDisguise] = useState(false);
  const [castForDash, setCastForDash] = useState(false);
  const [castForBlitz, setCastForBlitz] = useState(false);
  const [castForFreerunning, setCastForFreerunning] = useState(false);
  const [castForCleave, setCastForCleave] = useState(false);
  const [paidConspire, setPaidConspire] = useState(false);
  const [paidBargain, setPaidBargain] = useState(false);
  const [paidDemonstrate, setPaidDemonstrate] = useState(false);
  const [escalateExtraTargets, setEscalateExtraTargets] = useState(0);
  const [bargainSacrificeUid, setBargainSacrificeUid] = useState<string | null>(null);
  const [assistMana, setAssistMana] = useState(0);
  const [sneakLandHandIndices, setSneakLandHandIndices] = useState<number[]>([]);
  const [castForMiracle, setCastForMiracle] = useState(false);
  const [modalModeIndex, setModalModeIndex] = useState(0);
  const [pendingBoardAction, setPendingBoardAction] = useState<PendingBoardAction>(null);
  const [harmonizeCreatureIds, setHarmonizeCreatureIds] = useState<string[]>([]);
  const [pendingCastModifier, setPendingCastModifier] = useState<PendingCastModifier>(null);
  const [convokeCreatureIds, setConvokeCreatureIds] = useState<string[]>([]);
  const [delveGraveyardIndices, setDelveGraveyardIndices] = useState<number[]>([]);
  const [improviseArtifactIds, setImproviseArtifactIds] = useState<string[]>([]);
  const [emergeSacrificeUid, setEmergeSacrificeUid] = useState<string | null>(null);
  const [paidCasualty, setPaidCasualty] = useState(false);
  const [casualtySacrificeUid, setCasualtySacrificeUid] = useState<string | null>(null);
  const [pendingAlt, setPendingAlt] = useState<PendingAlt>(null);
  const [pendingGyAction, setPendingGyAction] = useState<PendingGyAction>(null);
  const [pendingExileAction, setPendingExileAction] = useState<PendingExileAction>(null);
  const [craftHostUid, setCraftHostUid] = useState<string | null>(null);
  const [craftArtifactIds, setCraftArtifactIds] = useState<string[]>([]);
  const [scavengeGyIdx, setScavengeGyIdx] = useState<number | null>(null);
  const [gyCastIdx, setGyCastIdx] = useState<number | null>(null);

  const logRef = useRef<HTMLDivElement>(null);

  // Clear targeting UI when the phase changes (e.g. into declare blockers).
  useEffect(() => {
    setSelectedHandIdx(null);
    setWaitingTarget(false);
    setTargetMode('none');
    setSelectedBlockerUid(null);
    setPendingLandPlay(null);
    setPendingFetchChoice(null);
    setActionError(null);
  }, [gs?.phase]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [gs?.log]);

  // Start the game once route query params are available.
  useEffect(() => {
    if (!router.isReady || !deckId || !vsArch) return;
    setLoading(true);
    startGame(Number(deckId), vsArch, format, playFirst)
      .then(state => { setGs(state); setLoading(false); })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, [router.isReady, deckId, vsArch, format, playFirst]);

  // Cleanup on unmount
  useEffect(() => {
    return () => { if (gs?.gameId) void deleteGame(gs.gameId); };
  }, [gs?.gameId]);

  const act = useCallback(async (action: string, opts: Record<string, unknown> = {}) => {
    if (!gs || actionInFlightRef.current) return;
    actionInFlightRef.current = true;
    setLoading(true);
    setSelectedHandIdx(null);
    setTargetMode('none');
    setWaitingTarget(false);
    setCastForEvoke(false);
    setCastForEmerge(false);
    setCastForSpectacle(false);
    setCastForMorph(false);
    setCastForDisguise(false);
    setCastForDash(false);
    setCastForBlitz(false);
    setCastForFreerunning(false);
    setCastForCleave(false);
    setPaidConspire(false);
    setPaidBargain(false);
    setPaidDemonstrate(false);
    setEscalateExtraTargets(0);
    setBargainSacrificeUid(null);
    setAssistMana(0);
    setSneakLandHandIndices([]);
    setCastForMiracle(false);
    setPendingBoardAction(null);
    setHarmonizeCreatureIds([]);
    setPaidCasualty(false);
    setCasualtySacrificeUid(null);
    setPendingCastModifier(null);
    setConvokeCreatureIds([]);
    setDelveGraveyardIndices([]);
    setImproviseArtifactIds([]);
    setEmergeSacrificeUid(null);
    setPendingAlt(null);
    setPendingGyAction(null);
    setPendingExileAction(null);
    setCraftHostUid(null);
    setCraftArtifactIds([]);
    setScavengeGyIdx(null);
    setGyCastIdx(null);
    setModalModeIndex(0);
    setPendingLandPlay(null);
    setPendingFetchChoice(null);
    setActionError(null);
    try {
      const next = await gameAction(gs.gameId, action, opts as Parameters<typeof gameAction>[2]);
      setGs(next);
      if (next.error) {
        setActionError(next.error);
      }
    } catch (e) {
      setActionError(actionErrorMessage(e));
    } finally {
      actionInFlightRef.current = false;
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
  const canEscape = gs?.availableActions.includes('cast_escape');
  const canScavenge = gs?.availableActions.includes('scavenge');
  const canDredge = gs?.availableActions.includes('dredge');
  const canSuspend = gs?.availableActions.includes('suspend');
  const canForetell = gs?.availableActions.includes('foretell');
  const canPlot = gs?.availableActions.includes('plot');
  const canCastMadness = gs?.availableActions.includes('cast_madness');
  const canForecast = gs?.availableActions.includes('forecast');
  const canCastForetell = gs?.availableActions.includes('cast_foretell');
  const canCastPlot = gs?.availableActions.includes('cast_plot');
  const canJumpStart = gs?.availableActions.includes('cast_jump_start');
  const canRetrace = gs?.availableActions.includes('cast_retrace');
  const canAftermath = gs?.availableActions.includes('cast_aftermath');
  const canHarmonize = gs?.availableActions.includes('cast_harmonize');
  const canTurnUpMorph = gs?.availableActions.includes('turn_up_morph');
  const canEmbalm = gs?.availableActions.includes('embalm');
  const _canAttack = gs?.availableActions.includes('go_to_attack') || phase === 'attack'; void _canAttack;
  const inCombat = phase === 'attack';
  const inBlocking = phase === 'declare_blockers';
  const opponentAttackers = gs?.opponentAttackers ?? [];
  const pendingBlockers = gs?.pendingBlockers ?? {};
  const canPassPriority = gs?.availableActions.includes('pass_priority') ?? false;
  const stackCount = gs?.stack?.length ?? 0;

  const selectedCard = selectedHandIdx !== null
    ? gs?.playerHand.find(card => card.idx === selectedHandIdx) ?? null
    : null;

  const applyScriptedModalTargeting = useCallback((card: CardInHand, modeIndex: number) => {
    const modeCount = card.scriptedModalModes ?? 0;
    if (!card.hasScriptedModal || modeCount <= 1) {
      return;
    }
    const label = scriptedModalLabels(card.oracle, modeCount)[modeIndex] ?? '';
    if (!modalNeedsTarget(label)) {
      setWaitingTarget(false);
      setTargetMode('none');
      return;
    }
    setWaitingTarget(true);
    setTargetMode(modalTargetMode(label));
  }, []);

  // ---- Handlers ----

  function handleHandClick(card: CardInHand) {
    if (busy) return;
    if (pendingLandPlay !== null && card.idx !== pendingLandPlay) return;
    if (pendingFetchChoice !== null) return;
    const handIdx = card.idx;
    if (pendingCastModifier === 'sneak' && selectedHandIdx !== null && card.isLand && handIdx !== selectedHandIdx) {
      setSneakLandHandIndices(prev =>
        prev.includes(handIdx) ? prev.filter(i => i !== handIdx) : [...prev, handIdx],
      );
      return;
    }
    if (pendingAlt === 'jump_discard' && gyCastIdx !== null) {
      void act('cast_jump_start', {
        handIdx: gyCastIdx,
        discardHandIdx: handIdx,
        targetPlayer: 1,
      });
      return;
    }
    if (pendingAlt === 'retrace_discard' && gyCastIdx !== null) {
      if (!card.isLand) return;
      void act('cast_retrace', {
        handIdx: gyCastIdx,
        discardHandIdx: handIdx,
        targetPlayer: 1,
      });
      return;
    }
    if (!(canPlayLand && card.isLand) && !card.affordable && !pendingAlt) return;
    if (card.isLand && canPlayLand) {
      if (card.hasShocklandEtb) {
        setPendingLandPlay(handIdx);
        setPendingFetchChoice(null);
        return;
      }
      void act('play_land', { handIdx, payShocklandLife: false });
      return;
    }
    if (!canCast) return;
    if (selectedHandIdx === handIdx) {
      setSelectedHandIdx(null);
      setTargetMode('none');
      setWaitingTarget(false);
      setCastForEvoke(false);
      setCastForEmerge(false);
      setCastForSpectacle(false);
      setCastForMorph(false);
      setCastForMiracle(false);
      setCastForCleave(false);
      setPaidConspire(false);
      setAssistMana(0);
      setPaidCasualty(false);
      setCasualtySacrificeUid(null);
      setPendingCastModifier(null);
      setConvokeCreatureIds([]);
      setDelveGraveyardIndices([]);
      setImproviseArtifactIds([]);
      setEmergeSacrificeUid(null);
      setHarmonizeCreatureIds([]);
      setPendingBoardAction(null);
      setPendingAlt(null);
      setPendingGyAction(null);
      setPendingExileAction(null);
      setModalModeIndex(0);
      return;
    }
    setSelectedHandIdx(handIdx);
    setCastForEvoke(false);
    setCastForEmerge(false);
    setCastForSpectacle(false);
    setCastForMorph(false);
    setCastForDisguise(false);
    setCastForDash(false);
    setCastForBlitz(false);
    setCastForFreerunning(false);
    setCastForCleave(false);
    setPaidConspire(false);
    setPaidBargain(false);
    setPaidDemonstrate(false);
    setEscalateExtraTargets(0);
    setBargainSacrificeUid(null);
    setAssistMana(0);
    setSneakLandHandIndices([]);
    setCastForMiracle(false);
    setPendingBoardAction(null);
    setHarmonizeCreatureIds([]);
    setPaidCasualty(false);
    setCasualtySacrificeUid(null);
    setPendingCastModifier(null);
    setConvokeCreatureIds([]);
    setDelveGraveyardIndices([]);
    setImproviseArtifactIds([]);
    setEmergeSacrificeUid(null);
    setPendingAlt(null);
    setPendingGyAction(null);
    setPendingExileAction(null);
    if (card.hasScriptedModal && (card.scriptedModalModes ?? 0) > 1) {
      setModalModeIndex(0);
      applyScriptedModalTargeting(card, 0);
    } else if (['burn', 'pump', 'removal'].includes(card.category)) {
      setWaitingTarget(true);
      setTargetMode(card.category === 'pump' ? 'self' : 'opp');
    } else if (
      oracleHas(card.oracle, 'Miracle')
      || oracleHas(card.oracle, 'Casualty')
      || card.hasEvoke
      || card.hasConvoke
      || card.hasDelve
      || card.hasImprovise
      || card.hasEmerge
      || card.hasSpectacle
      || card.hasMorph
      || card.hasDisguise
      || card.hasSneak
      || card.hasDash
      || card.hasBlitz
      || card.hasFreerunning
      || card.hasCleave
      || card.hasConspire
      || card.hasAssist
      || card.hasBargain
      || card.hasEscalate
      || card.hasDemonstrate
      || card.hasScriptedModal
    ) {
      // Wait for Cast / options before sending to server
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
    if (busy || selectedHandIdx === null || !selectedCard) return;
    if (paidCasualty && !casualtySacrificeUid) {
      setPendingAlt('casualty');
      setWaitingTarget(true);
      setTargetMode('self');
      return;
    }
    if (paidBargain && !bargainSacrificeUid) {
      setPendingAlt('bargain');
      setWaitingTarget(true);
      setTargetMode('self');
      return;
    }
    if (castForEmerge && !emergeSacrificeUid) {
      setPendingCastModifier('emerge');
      return;
    }
    void act('cast', {
      handIdx: selectedHandIdx,
      targetUid: opts.targetUid,
      targetPlayer: opts.targetPlayer ?? 1,
      castForEvoke,
      castForEmerge,
      castForSpectacle,
      castForMorph,
      castForDisguise,
      castForDash,
      castForBlitz,
      castForFreerunning,
      castForCleave,
      paidConspire,
      paidBargain,
      paidDemonstrate,
      escalateExtraTargets,
      bargainSacrificeIds: bargainSacrificeUid ? [bargainSacrificeUid] : [],
      assistMana,
      sneakLandHandIndices,
      castForMiracle,
      paidCasualty,
      casualtySacrificeIds: casualtySacrificeUid ? [casualtySacrificeUid] : [],
      convokeCreatureIds,
      delveGraveyardIndices,
      improviseArtifactIds,
      emergeSacrificeIds: emergeSacrificeUid ? [emergeSacrificeUid] : [],
      ...(selectedCard.hasScriptedModal && (selectedCard.scriptedModalModes ?? 0) > 1
        ? { modalModeIndex }
        : {}),
    });
  }

  function toggleCastModifier(mode: Exclude<PendingCastModifier, null>) {
    setPendingCastModifier(prev => (prev === mode ? null : mode));
  }

  function canSacrificeForEmerge(perm: PermanentOnBoard): boolean {
    if (perm.type.includes('Creature')) return true;
    if (!perm.type.includes('Artifact')) return false;
    if (!selectedCard) return false;
    return oracleHas(selectedCard.oracle, 'sacrifice an artifact or creature');
  }

  function handlePlayerBoardClick(perm: PermanentOnBoard) {
    if (busy) return;
    if (inBlocking) {
      if (perm.type.includes('Creature')) {
        if (pendingBlockers[perm.uid]) {
          void act('unassign_blocker', { blockerUid: perm.uid });
          return;
        }
        setSelectedBlockerUid(perm.uid);
      }
      return;
    }
    if ((phase === 'main1' || phase === 'main2') && isFetchland(perm) && !perm.tapped) {
      if (gs?.availableActions.includes('activate')) {
        void act('activate', { permanentUid: perm.uid, handIdx: 0 });
      }
      return;
    }
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
    if (pendingAlt === 'bargain') {
      if (!perm.type.includes('Artifact')) return;
      setBargainSacrificeUid(perm.uid);
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
    if (pendingAlt === 'scavenge_target') {
      if (scavengeGyIdx === null) return;
      void act('scavenge', { handIdx: scavengeGyIdx, targetUid: perm.uid });
      return;
    }
    if (pendingCastModifier === 'convoke') {
      if (!perm.type.includes('Creature') || perm.tapped) return;
      setConvokeCreatureIds(prev =>
        prev.includes(perm.uid) ? prev.filter(id => id !== perm.uid) : [...prev, perm.uid],
      );
      return;
    }
    if (pendingCastModifier === 'improvise') {
      if (!perm.type.includes('Artifact') || perm.tapped) return;
      setImproviseArtifactIds(prev =>
        prev.includes(perm.uid) ? prev.filter(id => id !== perm.uid) : [...prev, perm.uid],
      );
      return;
    }
    if (pendingCastModifier === 'emerge') {
      if (!canSacrificeForEmerge(perm)) return;
      setEmergeSacrificeUid(perm.uid);
      setPendingCastModifier(null);
      return;
    }
    if (pendingCastModifier === 'harmonize') {
      if (!perm.type.includes('Creature') || perm.tapped) return;
      setHarmonizeCreatureIds(prev =>
        prev.includes(perm.uid) ? [] : [perm.uid],
      );
      return;
    }
    if (pendingBoardAction === 'turn_up_morph') {
      if (!perm.faceDown) return;
      void act('turn_up_morph', { permanentUid: perm.uid });
      return;
    }
    if (waitingTarget && targetMode === 'self') {
      handleTargetPermanent(perm, false);
    } else if (inCombat && perm.canAttack) {
      void act('toggle_attacker', { permanentUid: perm.uid });
    }
  }

  function confirmCraft() {
    if (busy || !craftHostUid || craftArtifactIds.length === 0) return;
    void act('craft', { permanentUid: craftHostUid, craftArtifactIds });
  }

  function handleExileClick(idx: number) {
    if (busy || !pendingExileAction) return;
    void act(pendingExileAction, { handIdx: idx, targetPlayer: 1 });
  }

  function handleGraveyardClick(idx: number) {
    if (pendingCastModifier === 'delve') {
      setDelveGraveyardIndices(prev =>
        prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx],
      );
      return;
    }
    if (!pendingGyAction) return;
    if (pendingGyAction === 'scavenge') {
      setScavengeGyIdx(idx);
      setPendingGyAction(null);
      setPendingAlt('scavenge_target');
      setWaitingTarget(true);
      setTargetMode('self');
      return;
    }
    if (pendingGyAction === 'cast_jump_start') {
      setGyCastIdx(idx);
      setPendingGyAction(null);
      setPendingAlt('jump_discard');
      return;
    }
    if (pendingGyAction === 'cast_retrace') {
      setGyCastIdx(idx);
      setPendingGyAction(null);
      setPendingAlt('retrace_discard');
      return;
    }
    if (pendingGyAction === 'cast_harmonize') {
      if (busy) return;
      void act('cast_harmonize', {
        handIdx: idx,
        targetPlayer: 1,
        harmonizeCreatureIds,
      });
      return;
    }
    if (busy) return;
    void act(pendingGyAction, { handIdx: idx, targetPlayer: 1 });
  }

  function handleOpponentAttackerClick(perm: PermanentOnBoard) {
    if (busy || !inBlocking || !selectedBlockerUid) return;
    void act('assign_blocker', {
      blockerUid: selectedBlockerUid,
      attackerUid: perm.uid,
    });
    setSelectedBlockerUid(null);
  }

  function handleTargetPermanent(perm: PermanentOnBoard, isOppBoard: boolean) {
    if (busy || !waitingTarget || selectedHandIdx === null) return;
    if (pendingAlt === 'bloodrush' && !isOppBoard) {
      void act('bloodrush', { handIdx: selectedHandIdx, targetUid: perm.uid });
      return;
    }
    if (pendingAlt === 'ninjutsu' && !isOppBoard) {
      void act('ninjutsu', { handIdx: selectedHandIdx, targetUid: perm.uid });
      return;
    }
    if (pendingAlt === 'bargain' && !isOppBoard) {
      if (!perm.type.includes('Artifact')) return;
      setBargainSacrificeUid(perm.uid);
      setPendingAlt(null);
      setWaitingTarget(false);
      setTargetMode('none');
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
    setCastForEmerge(false);
    setCastForSpectacle(false);
    setCastForMorph(false);
    setCastForDisguise(false);
    setCastForDash(false);
    setCastForBlitz(false);
    setCastForFreerunning(false);
    setCastForCleave(false);
    setPaidConspire(false);
    setPaidBargain(false);
    setPaidDemonstrate(false);
    setEscalateExtraTargets(0);
    setBargainSacrificeUid(null);
    setAssistMana(0);
    setSneakLandHandIndices([]);
    setCastForMiracle(false);
    setPendingBoardAction(null);
    setHarmonizeCreatureIds([]);
    setPaidCasualty(false);
    setCasualtySacrificeUid(null);
    setPendingCastModifier(null);
    setConvokeCreatureIds([]);
    setDelveGraveyardIndices([]);
    setImproviseArtifactIds([]);
    setEmergeSacrificeUid(null);
    setPendingAlt(null);
    setPendingGyAction(null);
    setPendingExileAction(null);
    setCraftHostUid(null);
    setCraftArtifactIds([]);
    setScavengeGyIdx(null);
    setGyCastIdx(null);
    setModalModeIndex(0);
  }

  function handleTargetOpponent() {
    if (busy || !waitingTarget || selectedHandIdx === null || pendingAlt) return;
    castSelected({ targetPlayer: 1 });
  }

  function handleLibraryClick(entry: LibraryCardSummary) {
    if (busy || !gs?.fetchSearch) return;
    if (!gs.fetchSearch.fetchableNames.includes(entry.name)) return;
    if (entry.isShockland) {
      setPendingFetchChoice(entry);
      setPendingLandPlay(null);
      return;
    }
    void act('fetch_land', { libraryIdx: entry.libraryIdx, payShocklandLife: false });
  }

  function confirmLandPlay(payShocklandLife: boolean) {
    if (busy || pendingLandPlay === null) return;
    void act('play_land', { handIdx: pendingLandPlay, payShocklandLife });
    setPendingLandPlay(null);
  }

  function confirmFetchLand(payShocklandLife: boolean) {
    if (busy || !pendingFetchChoice) return;
    void act('fetch_land', {
      libraryIdx: pendingFetchChoice.libraryIdx,
      payShocklandLife,
    });
    setPendingFetchChoice(null);
  }

  const libraryTotal = gs?.playerLibrary?.reduce((sum, entry) => sum + entry.count, 0) ?? 0;

  // ---- Render ----

  if (!router.isReady) {
    return (
      <main style={{ padding: '2rem', color: '#eee', background: '#111', minHeight: '100vh' }}>
        <p>Loading…</p>
      </main>
    );
  }

  if (!deckId || !vsArch) {
    return (
      <main style={{ padding: '2rem', color: '#eee', background: '#111', minHeight: '100vh' }}>
        <h2>Missing parameters</h2>
        <p>Navigate here from the deck editor's Simulate tab.</p>
        <Link href="/" style={{ color: '#4a90d9' }}>Back to home</Link>
      </main>
    );
  }

  if (error) {
    return (
      <main style={{ padding: '2rem', color: '#eee', background: '#111', minHeight: '100vh' }}>
        <h2 style={{ color: '#e74c3c' }}>Error</h2>
        <pre style={{ color: '#aaa' }}>{error}</pre>
        <p style={{ color: '#888' }}>Make sure the sim service is running: <code>cd mtg-sim/sim && python main.py</code></p>
        <Link href="/" style={{ color: '#4a90d9' }}>Back to home</Link>
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
    <main style={{ background: '#111', minHeight: '100vh', color: '#eee', display: 'flex', flexDirection: 'column', marginRight: 300 }}>

      {/* Header bar */}
      <div style={{ background: '#1a1a2e', padding: '0.5rem 1rem', display: 'flex', alignItems: 'center', gap: 16, borderBottom: '1px solid #333' }}>
        <Link href={`/decks/${vsArch}`} style={{ color: '#aaa', fontSize: '0.85rem' }}>Back</Link>
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
            ) : gs.opponentBattlefield.map(p => {
              const isAttacking = opponentAttackers.some(attacker => attacker.uid === p.uid);
              const canAssignBlock = !busy && inBlocking && isAttacking && selectedBlockerUid !== null;
              const blockedBy = Object.entries(pendingBlockers).find(([, attackerUid]) => attackerUid === p.uid);
              return (
              <BoardCard
                key={p.uid}
                perm={p}
                dim={waitingTarget && targetMode !== 'opp' && !canAssignBlock}
                selected={canAssignBlock || Boolean(blockedBy)}
                statusLabel={blockedBy ? 'blocked' : undefined}
                onClick={
                  !busy && canAssignBlock
                    ? () => handleOpponentAttackerClick(p)
                    : !busy && waitingTarget && targetMode === 'opp'
                      ? () => handleTargetPermanent(p, true)
                      : undefined
                }
              />
            );})}
            {/* "Target opponent player" button when in burn mode */}
            {waitingTarget && targetMode === 'opp' && (
              <button type="button"
                disabled={busy}
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
          {(pendingAlt || pendingGyAction || pendingExileAction || pendingCastModifier) && (
            <span style={{ marginLeft: 'auto', color: '#f1c40f', fontWeight: 600, fontSize: '0.85rem' }}>
              {pendingAlt === 'bloodrush' && 'Bloodrush: click your creature to pump'}
              {pendingAlt === 'ninjutsu' && 'Ninjutsu: click your attacker to replace'}
              {pendingAlt === 'casualty' && 'Casualty: click a creature to sacrifice'}
              {pendingAlt === 'bargain' && 'Bargain: click an artifact to sacrifice'}
              {pendingAlt === 'boast' && 'Boast: click an attacking creature'}
              {pendingAlt === 'outlast' && 'Outlast: click a creature with outlast'}
              {pendingAlt === 'craft_host' && 'Craft: click the permanent to craft'}
              {pendingAlt === 'craft_artifacts' && 'Craft: click artifacts to exile, then confirm'}
              {pendingAlt === 'scavenge_target' && 'Scavenge: click a creature to receive counters'}
              {pendingAlt === 'jump_discard' && 'Jump-start: click a card in hand to discard'}
              {pendingAlt === 'retrace_discard' && 'Retrace: click a land in hand to discard'}
              {pendingGyAction === 'encore' && 'Encore: click a creature in your graveyard'}
              {pendingGyAction === 'eternalize' && 'Eternalize: click a creature in your graveyard'}
              {pendingGyAction === 'unearth' && 'Unearth: click a card in your graveyard'}
              {pendingGyAction === 'cast_disturb' && 'Disturb: click a creature in your graveyard'}
              {pendingGyAction === 'cast_flashback' && 'Flashback: click a card in your graveyard'}
              {pendingGyAction === 'cast_escape' && 'Escape: click a card in your graveyard'}
              {pendingGyAction === 'cast_jump_start' && 'Jump-start: click a card in your graveyard'}
              {pendingGyAction === 'cast_retrace' && 'Retrace: click a card in your graveyard'}
              {pendingGyAction === 'cast_aftermath' && 'Aftermath: click a card in your graveyard'}
              {pendingGyAction === 'cast_harmonize' && 'Harmonize: click a card in your graveyard'}
              {pendingGyAction === 'dredge' && 'Dredge: click a card with dredge in your graveyard'}
              {pendingGyAction === 'scavenge' && 'Scavenge: click a creature card in your graveyard'}
              {pendingExileAction === 'cast_foretell' && 'Foretell cast: click a foretold card in exile'}
              {pendingExileAction === 'cast_plot' && 'Plot cast: click a plotted card in exile'}
              {pendingCastModifier === 'convoke' && 'Convoke: click untapped creatures to help pay'}
              {pendingCastModifier === 'delve' && 'Delve: click graveyard cards to exile for mana'}
              {pendingCastModifier === 'improvise' && 'Improvise: click untapped artifacts to help pay'}
              {pendingCastModifier === 'emerge' && 'Emerge: click a permanent to sacrifice'}
              {pendingCastModifier === 'harmonize' && 'Harmonize: click a creature to tap for cost reduction'}
              {pendingCastModifier === 'sneak' && 'Sneak: click lands in hand to exile for mana'}
              {pendingBoardAction === 'turn_up_morph' && 'Morph/Disguise: click a face-down creature to turn face up'}
              {inBlocking && 'Click your creature, then an attacker to block (click assigned blocker to remove)'}
            </span>
          )}
          {actionError && (
            <span style={{ marginLeft: 'auto', color: '#e74c3c', fontSize: '0.82rem' }}>
              {actionError}
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
          ) : gs.playerBattlefield.map(p => {
            const blockingAttackerUid = pendingBlockers[p.uid];
            const blockingAttacker = blockingAttackerUid
              ? opponentAttackers.find(attacker => attacker.uid === blockingAttackerUid)
              : null;
            const boardInteractive = !busy && (
              pendingAlt
              || pendingCastModifier
              || pendingBoardAction
              || inBlocking
              || (waitingTarget && targetMode === 'self')
              || (inCombat && p.canAttack)
              || (
                (phase === 'main1' || phase === 'main2')
                && isFetchland(p)
                && !p.tapped
                && gs.availableActions.includes('activate')
              )
            );
            return (
            <BoardCard
              key={p.uid}
              perm={p}
              selected={
                gs.pendingAttackers.includes(p.uid)
                || selectedBlockerUid === p.uid
                || Boolean(blockingAttackerUid)
                || craftArtifactIds.includes(p.uid)
                || craftHostUid === p.uid
                || convokeCreatureIds.includes(p.uid)
                || improviseArtifactIds.includes(p.uid)
                || emergeSacrificeUid === p.uid
                || harmonizeCreatureIds.includes(p.uid)
              }
              statusLabel={
                blockingAttacker
                  ? `blocking ${blockingAttacker.name}`
                  : undefined
              }
              onClick={boardInteractive ? () => handlePlayerBoardClick(p) : undefined}
            />
          );})}
        </div>

        {(gs.playerExileCards?.length ?? 0) > 0 && pendingExileAction && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ color: '#888', fontSize: '0.78rem' }}>Exile:</span>
            {gs.playerExileCards!
              .filter(card => card.castMode === (pendingExileAction === 'cast_foretell' ? 'foretell' : 'plot'))
              .map(card => (
                <button
                  key={card.idx}
                  type="button"
                  onClick={() => handleExileClick(card.idx)}
                  style={btnStyle('#2c3e50')}
                >
                  [{card.idx}] {card.name}
                </button>
              ))}
          </div>
        )}

        {(gs.playerGraveyardCards?.length ?? 0) > 0 && (pendingGyAction || pendingCastModifier === 'delve') && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ color: '#888', fontSize: '0.78rem' }}>Graveyard:</span>
            {gs.playerGraveyardCards!.map(card => {
              const delveSelected = delveGraveyardIndices.includes(card.idx);
              return (
                <button
                  key={card.idx}
                  type="button"
                  onClick={() => handleGraveyardClick(card.idx)}
                  style={btnStyle(pendingCastModifier === 'delve' && delveSelected ? '#1a5276' : '#34495e')}
                >
                  [{card.idx}] {card.name}
                  {pendingCastModifier === 'delve' && delveSelected ? ' (delve)' : ''}
                </button>
              );
            })}
          </div>
        )}

        {/* Player life + mana */}
        <LifeBar label="You" life={gs.playerLife} mana={gs.playerMana} />

        {/* Action buttons */}
        {!isDone && !isOppTurn && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {canPassPriority && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void act('pass_priority')}
                style={btnStyle('#9b59b6')}
              >
                Pass priority{stackCount > 0 ? ` (${stackCount} on stack)` : ''}
              </button>
            )}

            {isMulligan && <>
              <button type="button" disabled={busy} onClick={() => void act('keep')} style={btnStyle('#27ae60')}>
                Keep hand ({gs.playerHand.length} cards)
              </button>
              <button type="button" onClick={() => void act('mulligan')} disabled={busy || gs.playerHand.length <= 4} style={btnStyle('#e67e22')}>
                Mulligan to {gs.playerHand.length - 1}
              </button>
            </>}

            {phase === 'draw' && (
              <>
                <button type="button" disabled={busy} onClick={() => void act('draw')} style={btnStyle('#4a90d9')}>
                  Draw card
                </button>
                {canDredge && (
                  <button type="button" onClick={() => setPendingGyAction('dredge')} style={btnStyle('#6c3483')}>
                    Dredge
                  </button>
                )}
              </>
            )}

            {phase === 'main1' && <>
              {!waitingTarget && (
                <button type="button" disabled={busy} onClick={() => void act('go_to_attack')} style={btnStyle('#e67e22')}>
                  Go to combat
                </button>
              )}
              <button type="button" disabled={busy} onClick={() => void act('end_turn')} style={btnStyle('#555')}>
                End turn
              </button>
            </>}

            {inCombat && <>
              <button type="button" onClick={() => void act('confirm_attack')} style={btnStyle('#e74c3c')} disabled={busy || gs.pendingAttackers.length === 0}>
                Attack ({gs.pendingAttackers.length} creatures)
              </button>
              <button type="button" disabled={busy} onClick={() => void act('skip_attack')} style={btnStyle('#555')}>
                Skip combat
              </button>
            </>}

            {phase === 'main2' && (
              <button type="button" disabled={busy} onClick={() => void act('end_turn')} style={btnStyle('#555')}>
                End turn
              </button>
            )}

            {inBlocking && (
              <>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void act('confirm_blocks')}
                  style={btnStyle('#27ae60')}
                >
                  Confirm blocks
                </button>
                {selectedBlockerUid && (
                  <button
                    type="button"
                    onClick={() => setSelectedBlockerUid(null)}
                    style={btnStyle('#555')}
                  >
                    Clear blocker
                  </button>
                )}
              </>
            )}

            {pendingLandPlay !== null && (
              <>
                <button type="button" disabled={busy} onClick={() => confirmLandPlay(false)} style={btnStyle('#8fbc8f')}>
                  Play tapped
                </button>
                <button
                  type="button"
                  onClick={() => confirmLandPlay(true)}
                  disabled={busy || (gs?.playerLife ?? 0) <= 2}
                  style={btnStyle('#27ae60')}
                >
                  Pay 2 life (untapped)
                </button>
                <button type="button" onClick={() => setPendingLandPlay(null)} style={btnStyle('#555')}>
                  Cancel
                </button>
              </>
            )}

            {pendingFetchChoice && (
              <>
                <button type="button" disabled={busy} onClick={() => confirmFetchLand(false)} style={btnStyle('#8fbc8f')}>
                  Fetch {pendingFetchChoice.name} tapped
                </button>
                <button
                  type="button"
                  onClick={() => confirmFetchLand(true)}
                  disabled={busy || (gs?.playerLife ?? 0) <= 2}
                  style={btnStyle('#27ae60')}
                >
                  Pay 2 life (untapped)
                </button>
                <button type="button" onClick={() => setPendingFetchChoice(null)} style={btnStyle('#555')}>
                  Cancel
                </button>
              </>
            )}

            {selectedCard && !isMulligan && !pendingLandPlay && !pendingFetchChoice && (
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
                {canCast && selectedCard.hasSpectacle && selectedCard.spectacleAvailable && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={castForSpectacle}
                      onChange={e => setCastForSpectacle(e.target.checked)}
                    />
                    Cast for Spectacle
                  </label>
                )}
                {canCast && selectedCard.hasMorph && selectedCard.isCreature && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={castForMorph}
                      onChange={e => {
                        setCastForMorph(e.target.checked);
                        if (e.target.checked) {
                          setCastForDisguise(false);
                        }
                      }}
                    />
                    Cast face down (Morph)
                  </label>
                )}
                {canCast && selectedCard.hasDisguise && selectedCard.isCreature && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={castForDisguise}
                      onChange={e => {
                        setCastForDisguise(e.target.checked);
                        if (e.target.checked) setCastForMorph(false);
                      }}
                    />
                    Cast face down (Disguise)
                  </label>
                )}
                {canCast && selectedCard.hasDash && selectedCard.isCreature && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={castForDash}
                      onChange={e => setCastForDash(e.target.checked)}
                    />
                    Cast for Dash
                  </label>
                )}
                {canCast && selectedCard.hasBlitz && selectedCard.isCreature && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={castForBlitz}
                      onChange={e => setCastForBlitz(e.target.checked)}
                    />
                    Cast for Blitz
                  </label>
                )}
                {canCast && selectedCard.hasFreerunning && selectedCard.freerunningAvailable && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={castForFreerunning}
                      onChange={e => setCastForFreerunning(e.target.checked)}
                    />
                    Cast for Freerunning
                  </label>
                )}
                {canCast && selectedCard.hasSneak && (
                  <button
                    type="button"
                    onClick={() => toggleCastModifier('sneak')}
                    style={btnStyle(pendingCastModifier === 'sneak' ? '#1f618d' : '#566573')}
                  >
                    Sneak ({sneakLandHandIndices.length} lands)
                  </button>
                )}
                {canCast && selectedCard.hasEmerge && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={castForEmerge}
                      onChange={e => {
                        setCastForEmerge(e.target.checked);
                        if (!e.target.checked) setEmergeSacrificeUid(null);
                      }}
                    />
                    Cast for Emerge
                    {emergeSacrificeUid && ' (sacrifice selected)'}
                  </label>
                )}
                {canCast && selectedCard.hasCleave && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={castForCleave}
                      onChange={e => setCastForCleave(e.target.checked)}
                    />
                    Cast for Cleave
                  </label>
                )}
                {canCast && selectedCard.hasConspire && selectedCard.conspireAvailable && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={paidConspire}
                      onChange={e => setPaidConspire(e.target.checked)}
                    />
                    Pay Conspire (+2, copy on stack)
                  </label>
                )}
                {canCast && selectedCard.hasAssist && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', color: '#ddd' }}>
                    Assist mana
                    <input
                      type="number"
                      min={0}
                      max={selectedCard.cmc}
                      value={assistMana}
                      onChange={e => {
                        const next = Math.max(0, Math.min(selectedCard.cmc, Number(e.target.value) || 0));
                        setAssistMana(next);
                      }}
                      style={{ width: 48, padding: '2px 4px' }}
                    />
                  </label>
                )}
                {canCast && selectedCard.hasBargain && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={paidBargain}
                      onChange={e => {
                        setPaidBargain(e.target.checked);
                        if (!e.target.checked) setBargainSacrificeUid(null);
                      }}
                    />
                    Pay Bargain
                    {bargainSacrificeUid && ' (artifact selected)'}
                  </label>
                )}
                {canCast && selectedCard.hasEscalate && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', color: '#ddd' }}>
                    Escalate extra targets
                    <input
                      type="number"
                      min={0}
                      max={4}
                      value={escalateExtraTargets}
                      onChange={e => {
                        const next = Math.max(0, Math.min(4, Number(e.target.value) || 0));
                        setEscalateExtraTargets(next);
                      }}
                      style={{ width: 48, padding: '2px 4px' }}
                    />
                  </label>
                )}
                {canCast && selectedCard.hasDemonstrate && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#ddd' }}>
                    <input
                      type="checkbox"
                      checked={paidDemonstrate}
                      onChange={e => setPaidDemonstrate(e.target.checked)}
                    />
                    Demonstrate (copy on stack)
                  </label>
                )}
                {canCast && selectedCard.hasConvoke && (
                  <button
                    type="button"
                    onClick={() => toggleCastModifier('convoke')}
                    style={btnStyle(pendingCastModifier === 'convoke' ? '#1f618d' : '#2874a6')}
                  >
                    Convoke ({convokeCreatureIds.length})
                  </button>
                )}
                {canCast && selectedCard.hasDelve && (
                  <button
                    type="button"
                    onClick={() => toggleCastModifier('delve')}
                    style={btnStyle(pendingCastModifier === 'delve' ? '#1f618d' : '#2874a6')}
                  >
                    Delve ({delveGraveyardIndices.length})
                  </button>
                )}
                {canCast && selectedCard.hasImprovise && (
                  <button
                    type="button"
                    onClick={() => toggleCastModifier('improvise')}
                    style={btnStyle(pendingCastModifier === 'improvise' ? '#1f618d' : '#2874a6')}
                  >
                    Improvise ({improviseArtifactIds.length})
                  </button>
                )}
                {canCast && castForEmerge && selectedCard.hasEmerge && !emergeSacrificeUid && (
                  <button
                    type="button"
                    onClick={() => setPendingCastModifier('emerge')}
                    style={btnStyle('#884ea0')}
                  >
                    Pick emerge sacrifice
                  </button>
                )}
                {canCast && selectedCard.hasScriptedModal && (selectedCard.scriptedModalModes ?? 0) > 1 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxWidth: 360 }}>
                    <span style={{ fontSize: '0.85rem', color: '#ddd' }}>Choose mode</span>
                    {scriptedModalLabels(selectedCard.oracle, selectedCard.scriptedModalModes ?? 0).map(
                      (label, index) => (
                        <label
                          key={`modal-${index}`}
                          style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 6,
                            fontSize: '0.85rem',
                            color: '#ddd',
                          }}
                        >
                          <input
                            type="radio"
                            name="scriptedModalMode"
                            checked={modalModeIndex === index}
                            onChange={() => {
                              setModalModeIndex(index);
                              applyScriptedModalTargeting(selectedCard, index);
                            }}
                          />
                          {label}
                        </label>
                      ),
                    )}
                  </div>
                )}
                {canCast && !waitingTarget && !selectedCard.isLand && (
                  <button
                    type="button"
                    disabled={busy || !selectedCard.affordable}
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
                    disabled={busy}
                    onClick={() => void act('cycle', { handIdx: selectedHandIdx! })}
                    style={btnStyle('#7f8c8d')}
                  >
                    Cycle
                  </button>
                )}
                {selectedCard.canForecast && canForecast && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void act('forecast', { handIdx: selectedHandIdx! })}
                    style={btnStyle('#1f618d')}
                  >
                    Forecast
                  </button>
                )}
                {selectedCard.hasEmbalm && canEmbalm && selectedHandIdx !== null && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void act('embalm', { handIdx: selectedHandIdx })}
                    style={btnStyle('#7f8c8d')}
                  >
                    Embalm
                  </button>
                )}
                {selectedCard.canChannel && canChannel && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void act('channel', { handIdx: selectedHandIdx!, targetPlayer: 1 })}
                    style={btnStyle('#16a085')}
                  >
                    Channel
                  </button>
                )}
                {selectedCard.canSuspend && canSuspend && (
                  <button
                    type="button"
                    disabled={busy || !selectedCard.suspendAffordable}
                    onClick={() => void act('suspend', { handIdx: selectedHandIdx! })}
                    style={btnStyle('#5b2c6f')}
                  >
                    Suspend
                  </button>
                )}
                {selectedCard.canForetell && canForetell && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void act('foretell', { handIdx: selectedHandIdx! })}
                    style={btnStyle('#1f618d')}
                  >
                    Foretell
                  </button>
                )}
                {selectedCard.canPlot && canPlot && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void act('plot', { handIdx: selectedHandIdx! })}
                    style={btnStyle('#117a65')}
                  >
                    Plot
                  </button>
                )}
                {selectedCard.hasMadness && canCastMadness && (
                  <button
                    type="button"
                    disabled={busy || !selectedCard.madnessAffordable}
                    onClick={() => void act('cast_madness', { handIdx: selectedHandIdx!, targetPlayer: 1 })}
                    style={btnStyle('#922b21')}
                  >
                    Cast for Madness
                  </button>
                )}
              </>
            )}

            {!selectedCard && !waitingTarget && !pendingAlt && !pendingGyAction && !pendingExileAction && (
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
                {canEscape && (
                  <button type="button" onClick={() => setPendingGyAction('cast_escape')} style={btnStyle('#1a5276')}>
                    Escape
                  </button>
                )}
                {canScavenge && (
                  <button type="button" onClick={() => setPendingGyAction('scavenge')} style={btnStyle('#784212')}>
                    Scavenge
                  </button>
                )}
                {canJumpStart && (
                  <button type="button" onClick={() => setPendingGyAction('cast_jump_start')} style={btnStyle('#6c3483')}>
                    Jump-start
                  </button>
                )}
                {canRetrace && (
                  <button type="button" onClick={() => setPendingGyAction('cast_retrace')} style={btnStyle('#7d6608')}>
                    Retrace
                  </button>
                )}
                {canAftermath && (
                  <button type="button" onClick={() => setPendingGyAction('cast_aftermath')} style={btnStyle('#566573')}>
                    Aftermath
                  </button>
                )}
                {canHarmonize && (
                  <button type="button" onClick={() => setPendingGyAction('cast_harmonize')} style={btnStyle('#5d6d7e')}>
                    Harmonize
                  </button>
                )}
                {canTurnUpMorph && (
                  <button type="button" onClick={() => setPendingBoardAction('turn_up_morph')} style={btnStyle('#6e2c00')}>
                    Turn face up (Morph)
                  </button>
                )}
                {canCastForetell && (
                  <button type="button" onClick={() => setPendingExileAction('cast_foretell')} style={btnStyle('#1f618d')}>
                    Cast Foretell
                  </button>
                )}
                {canCastPlot && (
                  <button type="button" onClick={() => setPendingExileAction('cast_plot')} style={btnStyle('#117a65')}>
                    Cast Plot
                  </button>
                )}
              </>
            )}

            {pendingGyAction === 'cast_harmonize' && (
              <button
                type="button"
                onClick={() => toggleCastModifier('harmonize')}
                style={btnStyle(pendingCastModifier === 'harmonize' ? '#1f618d' : '#566573')}
              >
                Tap creature for harmonize ({harmonizeCreatureIds.length})
              </button>
            )}

            {pendingAlt === 'craft_artifacts' && (
              <button
                type="button"
                disabled={busy || !craftHostUid || craftArtifactIds.length === 0}
                onClick={confirmCraft}
                style={btnStyle('#16a085')}
              >
                Confirm craft ({craftArtifactIds.length} artifacts)
              </button>
            )}

            {(waitingTarget || pendingAlt || pendingGyAction || pendingExileAction || pendingCastModifier || pendingBoardAction) && (
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
            {gs.playerHand.map((card) => {
              const handIdx = card.idx;
              const isSelectable = !busy && (
                isMulligan
                || pendingAlt === 'jump_discard'
                || (pendingAlt === 'retrace_discard' && card.isLand)
                || (canPlayLand && card.isLand)
                || (!card.isLand && card.affordable)
              );
              return (
                <CardChip
                  key={`${card.name}-${handIdx}`}
                  card={card}
                  selected={selectedHandIdx === handIdx || sneakLandHandIndices.includes(handIdx)}
                  dimmed={!isMulligan && !isSelectable}
                  onClick={!isMulligan && isSelectable ? () => handleHandClick(card) : undefined}
                />
              );
            })}
          </div>
        </div>

      </div>

      {/* Library + log sidebar */}
      <div style={{
        position: 'fixed', right: 0, top: 0, bottom: 0,
        width: 300, background: '#161620', borderLeft: '1px solid #2a2a3a',
        display: 'flex', flexDirection: 'column', fontSize: '0.75rem',
      }}>
        <div style={{
          padding: '0.4rem 0.6rem',
          borderBottom: '1px solid #2a2a3a',
          color: '#888',
          fontWeight: 600,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <span>Library ({libraryTotal})</span>
          {gs.fetchSearch && (
            <span style={{ color: '#2ecc71', fontSize: '0.7rem' }}>Search active</span>
          )}
        </div>
        <div style={{ maxHeight: '42vh', overflow: 'auto', padding: '0.35rem 0.5rem', borderBottom: '1px solid #2a2a3a' }}>
          {(gs.playerLibrary ?? []).length === 0 ? (
            <div style={{ color: '#555', padding: '0.25rem 0.35rem' }}>Library empty</div>
          ) : (gs.playerLibrary ?? []).map(entry => {
            const fetchable = gs.fetchSearch?.fetchableNames.includes(entry.name) ?? false;
            const selected = pendingFetchChoice?.name === entry.name;
            const clickable = !busy && Boolean(gs.fetchSearch && fetchable);
            return (
              <div
                key={entry.name}
                onClick={clickable ? () => handleLibraryClick(entry) : undefined}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 8,
                  padding: '0.28rem 0.4rem',
                  borderRadius: 4,
                  cursor: clickable ? 'pointer' : 'default',
                  background: selected ? '#3a3000' : fetchable ? '#1a2a1a' : 'transparent',
                  border: selected ? '1px solid #f1c40f' : fetchable ? '1px solid #2ecc71' : '1px solid transparent',
                  color: fetchable ? '#ddd' : '#888',
                  marginBottom: 2,
                }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entry.name}</span>
                <span style={{ color: '#aaa', flexShrink: 0 }}>{entry.count}</span>
              </div>
            );
          })}
        </div>
        {gs.fetchSearch && (
          <div style={{ padding: '0.35rem 0.6rem', borderBottom: '1px solid #2a2a3a', color: '#2ecc71', fontSize: '0.72rem' }}>
            Click a highlighted land to fetch. Shocklands can enter untapped for 2 life.
            <button
              type="button"
              disabled={busy}
              onClick={() => void act('cancel_fetch')}
              style={{ ...btnStyle('#555'), marginTop: 6, width: '100%', fontSize: '0.72rem' }}
            >
              Cancel search
            </button>
          </div>
        )}
        {(gs.stack ?? []).length > 0 && (
          <div style={{ borderBottom: '1px solid #2a2a3a' }}>
            <div style={{
              padding: '0.4rem 0.6rem',
              color: '#888',
              fontWeight: 600,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}>
              <span>Stack ({gs.stack!.length})</span>
              {canPassPriority && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void act('pass_priority')}
                  style={{ ...btnStyle('#9b59b6'), padding: '0.15rem 0.45rem', fontSize: '0.68rem' }}
                >
                  Pass
                </button>
              )}
            </div>
            <div style={{ maxHeight: '18vh', overflow: 'auto', padding: '0 0.5rem 0.35rem' }}>
              {(gs.stack ?? []).map((entry, i) => {
                const who = entry.controller === 0 ? 'You' : 'Opponent';
                const label = entry.name ?? entry.type;
                return (
                  <div
                    key={`${label}-${i}`}
                    style={{
                      padding: '0.28rem 0.4rem',
                      marginBottom: 2,
                      borderRadius: 4,
                      background: entry.controller === 0 ? '#1a2a3a' : '#2a1a1a',
                      border: `1px solid ${entry.controller === 0 ? '#4a90d9' : '#e74c3c'}`,
                      color: '#ddd',
                    }}
                  >
                    <span style={{ color: entry.controller === 0 ? '#4a90d9' : '#e74c3c', fontWeight: 600 }}>
                      {who}
                    </span>
                    {' — '}
                    {label}
                  </div>
                );
              })}
            </div>
          </div>
        )}
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
