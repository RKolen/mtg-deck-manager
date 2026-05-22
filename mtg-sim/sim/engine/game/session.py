"""Game session registry and factory."""

from __future__ import annotations

import random
import uuid

from deck_registry import CardInfo
from engine.core.game_state import GameState, PlayerInfo
from engine.core.turn_structure import TurnRunner
from engine.core.zones import ZoneManager
from engine.game.helpers import expand_deck
from engine.game.interactive import InteractiveGame
from engine.rules.stack import Stack

_sessions: dict[str, InteractiveGame] = {}


def create_game(
    player_cards: list[CardInfo],
    opponent_cards: list[CardInfo],
    player_name: str = "Player",
    opponent_name: str = "Opponent",
    on_the_play: bool = True,
) -> InteractiveGame:
    """Create and register a new interactive game session."""
    zones = ZoneManager()
    zones.player_zones[0].library = expand_deck(player_cards, 0)
    zones.player_zones[1].library = expand_deck(opponent_cards, 1)
    random.shuffle(zones.player_zones[0].library)
    random.shuffle(zones.player_zones[1].library)
    runner = TurnRunner()
    runner.begin_turn(0)
    state = GameState(
        game_id=str(uuid.uuid4()),
        zones=zones,
        players=[PlayerInfo(player_name), PlayerInfo(opponent_name)],
        turn=runner,
        stack=Stack(),
    )
    game = InteractiveGame(state=state, on_the_play=on_the_play)
    game.deal_opening_hands()
    _sessions[state.game_id] = game
    return game


def get_game(game_id: str) -> InteractiveGame | None:
    """Retrieve an active game session by ID."""
    return _sessions.get(game_id)


def remove_game(game_id: str) -> None:
    """Remove a game session from the store."""
    _sessions.pop(game_id, None)
