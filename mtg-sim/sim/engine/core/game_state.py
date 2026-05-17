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

from engine.core.game_object import Permanent
from engine.core.mana import ManaPool
from engine.core.turn_structure import TurnRunner
from engine.core.turn_structure import Step
from engine.core.zones import ZoneManager, ZoneMoveEvent
from engine.rules.state_based import check_sbas
from engine.rules.stack import Stack
from engine.rules.triggers import AttackTriggerEvent, StepTriggerEvent, TriggerRegistry


@dataclass
class PlayerInfo:
    """Per-player state that lives outside the zone system."""

    name: str
    life: int = 20
    poison: int = 0
    mana_pool: ManaPool = field(default_factory=ManaPool)
    land_played: bool = False
    spells_cast_this_turn: int = 0
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
