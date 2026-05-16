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

from engine.core.mana import ManaPool
from engine.core.turn_structure import TurnRunner
from engine.core.zones import ZoneManager
from engine.rules.stack import Stack


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
    log: list[LogEntry] = field(default_factory=list)
    winner: int | None = None

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
