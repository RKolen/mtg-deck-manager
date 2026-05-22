"""
Central game state for the MTG rules engine.

GameState is a pure data container: it holds every mutable piece of game
information but contains no action logic. The game loop (engine/game.py,
Phase B) reads and writes it; the rules modules (stack, SBAs, combat, …)
receive it as a parameter.

PlayerInfo tracks per-player mutable state that is not tracked by ZoneManager
(life, poison, mana pool, land-played flag).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.core.game_object import CardObject, Permanent, Target
from engine.core.mana import ManaPool
from engine.core.turn_structure import TurnRunner
from engine.core.turn_structure import Step
from engine.core.zones import ZoneManager, ZoneMoveEvent
from engine.abilities.keywords import enters_ready, has_persist, has_undying
from engine.rules.state_based import check_sbas
from engine.rules.stack import Stack
from engine.rules.triggers import AttackTriggerEvent, BlockTriggerEvent
from engine.rules.triggers import CombatDamageTriggerEvent
from engine.rules.triggers import LifeGainedTriggerEvent
from engine.rules.triggers import StepTriggerEvent, TriggerRegistry, spell_cast_event


@dataclass
class PlayerInfo:
    """Per-player state that lives outside the zone system."""

    name: str
    life: int = 20
    poison: int = 0
    mana_pool: ManaPool = field(default_factory=ManaPool)
    land_played: bool = False
    spells_cast_this_turn: int = 0
    combat_damage_dealt_this_turn: bool = False
    has_lost: bool = False


@dataclass
class LogEntry:
    """One timestamped line in the game log."""

    turn: int
    actor: str
    action: str
    detail: str = ""


@dataclass
class GameState:
    """All mutable state for one game session.

    Modules that implement rules receive a GameState and may mutate it.
    The game loop in engine/game.py (Phase B) owns the game-id → GameState
    mapping and is the only caller of action methods.
    """

    game_id: str
    zones: ZoneManager
    players: list[PlayerInfo]
    turn: TurnRunner
    stack: Stack
    trigger_registry: TriggerRegistry = field(default_factory=TriggerRegistry)
    log: list[LogEntry] = field(default_factory=list)
    winner: int | None = None

    def __post_init__(self) -> None:
        """Subscribe the trigger registry to zone movement events."""
        self.zones.register_listener(self._handle_zone_move)

    @property
    def active_player_idx(self) -> int:
        """Index of the player whose turn it currently is."""
        return self.turn.active_player_idx

    @property
    def non_active_player_idx(self) -> int:
        """Index of the player whose turn it is NOT."""
        return 1 - self.active_player_idx

    def log_event(self, actor: str, action: str, detail: str = "") -> None:
        """Append one entry to the game log."""
        self.log.append(LogEntry(
            turn=self.turn.context.turn_number,
            actor=actor,
            action=action,
            detail=detail,
        ))

    def check_sbas(self) -> list:
        """Apply state-based actions and return the emitted SBA events."""
        return check_sbas(self)

    def try_keyword_death_replacement(self, perm: Permanent) -> bool:
        """Apply persist/undying instead of destroying a creature; return True if replaced."""
        if 'Creature' not in perm.type_line or perm.is_token:
            return False
        if has_persist(perm) and perm.counters.get('-1/-1', 0) == 0:
            perm.counters['-1/-1'] = 1
            perm.damage_marked = 0
            self.log_event('rules', 'persist', f'{perm.name} returned with -1/-1')
            return True
        if has_undying(perm) and perm.counters.get('+1/+1', 0) == 0:
            perm.counters['+1/+1'] = 1
            perm.damage_marked = 0
            perm.sick = not enters_ready(perm)
            self.log_event('rules', 'undying', f'{perm.name} returned with +1/+1')
            return True
        return False

    def _handle_zone_move(self, event: ZoneMoveEvent) -> None:
        """Put matching triggered abilities on the stack."""
        self.trigger_registry.put_triggers_on_stack(event, self)

    def fire_step_triggers(self, step: Step) -> None:
        """Put triggered abilities for the beginning of a step on the stack."""
        event = StepTriggerEvent(
            step=step,
            active_player_idx=self.active_player_idx,
        )
        self.trigger_registry.put_triggers_on_stack(event, self)

    def fire_attack_triggers(self, attacker: Permanent) -> None:
        """Put triggered abilities for a declared attacker on the stack."""
        event = AttackTriggerEvent(
            attacker_id=attacker.obj_id,
            attacking_player_idx=attacker.controller_idx,
        )
        self.trigger_registry.put_triggers_on_stack(event, self)

    def fire_block_triggers(self, blocker: Permanent, attacker: Permanent) -> None:
        """Put triggered abilities for a declared blocker on the stack."""
        event = BlockTriggerEvent(
            blocker_id=blocker.obj_id,
            attacker_id=attacker.obj_id,
            defending_player_idx=blocker.controller_idx,
        )
        self.trigger_registry.put_triggers_on_stack(event, self)

    def fire_spell_cast_triggers(
        self,
        spell: CardObject,
        targets: tuple[Target, ...] = (),
    ) -> None:
        """Put triggered abilities for a cast spell on the stack."""
        self.trigger_registry.put_triggers_on_stack(
            spell_cast_event(spell, targets),
            self,
        )

    def gain_life(
        self,
        player_idx: int,
        amount: int,
        source_permanent_id: int | None = None,
    ) -> None:
        """Gain life and put matching life-gain triggers on the stack."""
        if amount <= 0:
            return
        self.players[player_idx].life += amount
        self.trigger_registry.put_triggers_on_stack(
            LifeGainedTriggerEvent(
                player_idx=player_idx,
                amount=amount,
                source_permanent_id=source_permanent_id,
            ),
            self,
        )

    def fire_combat_damage_triggers(
        self,
        source: Permanent,
        amount: int,
        damaged_player_idx: int | None = None,
        damaged_permanent: Permanent | None = None,
    ) -> None:
        """Put triggered abilities for combat damage dealt by a permanent on the stack."""
        if amount <= 0:
            return
        self.trigger_registry.put_triggers_on_stack(
            CombatDamageTriggerEvent(
                source_permanent_id=source.obj_id,
                controller_idx=source.controller_idx,
                amount=amount,
                damaged_player_idx=damaged_player_idx,
                damaged_permanent_id=(
                    damaged_permanent.obj_id if damaged_permanent is not None else None
                ),
            ),
            self,
        )

    def to_client(self) -> dict:
        """Serialise public game state, hiding the opponent's hand contents."""
        return {
            "gameId": self.game_id,
            "turn": self.turn.context.turn_number,
            "turnState": self.turn.to_dict(),
            "phase": self.turn.current_step.value,
            "winner": self.winner,
            "player": self._player_to_client(0, reveal_hand=True),
            "opponent": self._player_to_client(1, reveal_hand=False),
            "battlefield": {
                "player": [p.to_dict() for p in self.zones.permanents_of(0)],
                "opponent": [p.to_dict() for p in self.zones.permanents_of(1)],
            },
            "stack": self.stack.to_client(),
            "log": [entry.__dict__ for entry in self.log],
        }

    def _player_to_client(self, player_idx: int, reveal_hand: bool) -> dict:
        """Serialise one player's public state."""
        zones = self.zones.player_zones[player_idx]
        player = self.players[player_idx]
        data = {
            "name": player.name,
            "life": player.life,
            "poison": player.poison,
            "manaPool": player.mana_pool.total(),
            "landPlayed": player.land_played,
            "graveyard": [_card_name(c) for c in zones.graveyard],
            "libraryCount": len(zones.library),
            "handCount": len(zones.hand),
        }
        if reveal_hand:
            data["hand"] = [_card_name(c) for c in zones.hand]
        return data


def _card_name(card: object) -> str:
    """Return a display name for a CardObject-like value."""
    card_info = getattr(card, "card_info", None)
    return getattr(card_info, "name", "")
