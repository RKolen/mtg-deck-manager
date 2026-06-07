"""
Shared data classes for the MTG simulation engine.

Separating these from forge_adapter keeps each module within pylint line limits.
All public names are re-exported from forge_adapter for backward compatibility.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Public turn / game log types
# ---------------------------------------------------------------------------

@dataclass
class TurnBoard:
    """Board state snapshot for one player's turn."""

    hand_size: int = 0
    hand_cards: str = ""
    creatures_in_play: int = 0
    power: int = 0


@dataclass
class TurnDamage:
    """Damage dealt by one player during a single turn."""

    total: int = 0
    combat: int = 0
    noncombat: int = 0


@dataclass
class TurnEvent:
    """One player's full turn within a game."""

    turn: int
    player: int
    mana_available: int
    plays: list[str]
    life_totals: list[int]
    board: TurnBoard
    damage: TurnDamage

    @property
    def hand_size(self) -> int:
        """Hand size at end of turn."""
        return self.board.hand_size

    @property
    def creatures_in_play(self) -> int:
        """Creatures on the battlefield at end of turn."""
        return self.board.creatures_in_play

    @property
    def board_power(self) -> int:
        """Total power of attacking creatures this turn."""
        return self.board.power

    @property
    def damage_dealt(self) -> int:
        """Total damage dealt to opponent."""
        return self.damage.total

    @property
    def combat_damage(self) -> int:
        """Combat damage dealt to opponent."""
        return self.damage.combat

    @property
    def noncombat_damage(self) -> int:
        """Non-combat damage dealt to opponent."""
        return self.damage.noncombat


@dataclass
class GameLogOutcome:
    """Final outcome of a single simulated game."""

    winner: int
    final_turn: int
    win_condition: str


@dataclass
class GameLogSetup:
    """Setup information for a single simulated game."""

    game_index: int
    on_the_play: bool


@dataclass
class GameLogMulligans:
    """Mulligan counts for both players in one game."""

    player: int = 0
    opponent: int = 0


@dataclass
class GameLogLife:
    """Final life totals for both players."""

    player: int
    opponent: int


@dataclass
class PilotNotesGroup:
    """Pilot LLM log lines captured from Forge stdout."""

    all_notes: list[str] = field(default_factory=list)
    player: list[str] = field(default_factory=list)
    opponent: list[str] = field(default_factory=list)


@dataclass
class GameLog:
    """Complete record of a single simulated game."""

    setup: GameLogSetup
    mulligans: GameLogMulligans
    player_opening_hand: list[str]
    turns: list[TurnEvent]
    outcome: GameLogOutcome
    life: GameLogLife
    pilots: PilotNotesGroup = field(default_factory=PilotNotesGroup)

    @property
    def pilot_notes(self) -> list[str]:
        """All pilot log lines (both decks)."""
        return self.pilots.all_notes

    @property
    def player_pilot_notes(self) -> list[str]:
        """Pilot log lines for the simulated player deck."""
        return self.pilots.player

    @property
    def opponent_pilot_notes(self) -> list[str]:
        """Pilot log lines for the opponent deck."""
        return self.pilots.opponent

    @property
    def game_index(self) -> int:
        """Game index within the simulation batch."""
        return self.setup.game_index

    @property
    def on_the_play(self) -> bool:
        """True when this player was on the play."""
        return self.setup.on_the_play

    @property
    def player_mulligan(self) -> int:
        """Number of mulligans taken by the player."""
        return self.mulligans.player

    @property
    def opponent_mulligan(self) -> int:
        """Number of mulligans taken by the opponent."""
        return self.mulligans.opponent

    @property
    def winner(self) -> int:
        """Index of the winning player (0 or 1)."""
        return self.outcome.winner

    @property
    def final_turn(self) -> int:
        """Turn number on which the game ended."""
        return self.outcome.final_turn

    @property
    def win_condition(self) -> str:
        """String describing how the game was won."""
        return self.outcome.win_condition

    @property
    def player_final_life(self) -> int:
        """Player life total when the game ended."""
        return self.life.player

    @property
    def opponent_final_life(self) -> int:
        """Opponent life total when the game ended."""
        return self.life.opponent


@dataclass
class SimResultLife:
    """Life totals at the end of one game."""

    player: int = 0
    opponent: int = 0


@dataclass
class SimResultMulligans:
    """Mulligan counts at the end of one game."""

    player: int = 0
    opponent: int = 0


@dataclass
class SimResultOutcome:
    """Core outcome fields for one simulated game."""

    winner: int = 0
    timed_out: bool = False


@dataclass
class SimResult:
    """Outcome of a single simulated game — passed to sim_statistics."""

    outcome: SimResultOutcome
    turns: Optional[int]
    life: SimResultLife
    key_cards_on_loss: list[str] = field(default_factory=list)
    on_the_play: bool = True
    mulligans: SimResultMulligans = field(default_factory=SimResultMulligans)
    log: Optional[GameLog] = None

    @property
    def winner(self) -> int:
        """Index of the winning player (0 or 1)."""
        return self.outcome.winner

    @property
    def timed_out(self) -> bool:
        """True when the game was stopped due to timeout."""
        return self.outcome.timed_out

    @property
    def player_life(self) -> int:
        """Player's life total at game end."""
        return self.life.player

    @property
    def opponent_life(self) -> int:
        """Opponent's life total at game end."""
        return self.life.opponent

    @property
    def player_mulligan(self) -> int:
        """Number of mulligans taken by the player."""
        return self.mulligans.player

    @property
    def opponent_mulligan(self) -> int:
        """Number of mulligans taken by the opponent."""
        return self.mulligans.opponent

    @property
    def player_won(self) -> bool:
        """True when the player (index 0) won this game."""
        return self.outcome.winner == 0


# ---------------------------------------------------------------------------
# Internal parser helpers
# ---------------------------------------------------------------------------

@dataclass
class _TurnMeta:
    """Per-turn identification fields for the verbose parser."""

    game_turn: int = 0
    half_player: int = -1
    turn_num: Optional[int] = None


@dataclass
class _TurnAccum:
    """Per-turn accumulator for plays and damage during parsing."""

    plays: list[str] = field(default_factory=list)
    dmg: int = 0
    combat_dmg: int = 0
    noncombat_dmg: int = 0
    p_lands: int = 0


@dataclass
class _LifePair:
    """Life totals for both players during parsing."""

    p: int = 20
    o: int = 20


@dataclass
class _GameOutcome:
    """Aggregated outcome of a single mock game loop."""

    winner: int
    final_turn: int
    win_condition: str
    player_opening_hand: list[str]
    turn_events: list[TurnEvent]
    on_the_play: bool = False
    game_index: int = 0


@dataclass
class _ForgeParseExtras:
    """Forge verbose parser counters not tied to a single turn."""

    opp_dmg: Counter[str] = field(default_factory=Counter)
    pilot_notes: list[str] = field(default_factory=list)
    player_pilot_notes: list[str] = field(default_factory=list)
    opponent_pilot_notes: list[str] = field(default_factory=list)
    attack_by_turn: dict[tuple[int, int], int] = field(default_factory=dict)
    hand_by_turn: dict[tuple[int, int], int] = field(default_factory=dict)
    hand_cards_by_turn: dict[tuple[int, int], str] = field(default_factory=dict)


@dataclass
class _GameState:
    """Mutable per-game state used by _ForgeVerboseParser."""

    meta: _TurnMeta = field(default_factory=_TurnMeta)
    win_cond: str = ""
    life: _LifePair = field(default_factory=_LifePair)
    mulls: list[int] = field(default_factory=lambda: [0, 0])
    accum: _TurnAccum = field(default_factory=_TurnAccum)
    extras: _ForgeParseExtras = field(default_factory=_ForgeParseExtras)
    turn_events: list[TurnEvent] = field(default_factory=list)
