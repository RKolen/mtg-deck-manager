"""Game session registry and factory."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field

from deck_registry import CardInfo
from engine.core.game_state import GameState, LogEntry, PlayerInfo
from engine.core.turn_structure import TurnRunner
from engine.core.zones import ZoneManager
from engine.abilities.keywords.other.companion import validate_companion_deck
from engine.game.helpers import expand_deck
from engine.game.interactive import InteractiveGame, _GameSetup
from engine.rules.stack import Stack
from pilot_prompts import get_pilot_prompt

_sessions: dict[str, InteractiveGame] = {}


@dataclass
class _GameConfig:
    """Optional game setup parameters."""

    player_name: str = "Player"
    opponent_name: str = "Opponent"
    on_the_play: bool = True
    pilot_prompt: str = field(default="")
    player_pilot_prompt: str = field(default="")


def create_game(
    player_cards: list[CardInfo],
    opponent_cards: list[CardInfo],
    config: _GameConfig | None = None,
) -> InteractiveGame:
    """Create and register a new interactive game session."""
    cfg = config or _GameConfig()
    companion_err = validate_companion_deck(player_cards)
    zones = ZoneManager()
    zones.player_zones[0].library.extend(expand_deck(player_cards, 0))
    zones.player_zones[1].library.extend(expand_deck(opponent_cards, 1))
    random.shuffle(zones.player_zones[0].library)
    random.shuffle(zones.player_zones[1].library)
    runner = TurnRunner()
    runner.begin_turn(0)
    state = GameState(
        game_id=str(uuid.uuid4()),
        zones=zones,
        players=[PlayerInfo(cfg.player_name), PlayerInfo(cfg.opponent_name)],
        turn=runner,
        stack=Stack(),
    )
    game = InteractiveGame(
        state=state,
        _setup=_GameSetup(
            on_the_play=cfg.on_the_play,
            pilot_prompt=get_pilot_prompt(cfg.opponent_name, cfg.pilot_prompt),
            player_pilot_prompt=cfg.player_pilot_prompt.strip(),
        ),
    )
    game.deal_opening_hands()
    if companion_err:
        state.log.append(
            LogEntry(
                turn=state.turn.context.turn_number,
                actor='system',
                action='companion',
                detail=companion_err,
            )
        )
    _sessions[state.game_id] = game
    return game


def get_game(game_id: str) -> InteractiveGame | None:
    """Retrieve an active game session by ID."""
    return _sessions.get(game_id)


def remove_game(game_id: str) -> None:
    """Remove a game session from the store."""
    _sessions.pop(game_id, None)
