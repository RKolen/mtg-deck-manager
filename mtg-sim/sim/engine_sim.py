"""Headless simulation runner using the interactive Python game engine.

Drives both players automatically so that the full game runs without human input.

This engine is opt-in via ``engine=python`` on POST /simulate. The default
``auto`` engine uses Forge for full rules fidelity, realistic mulligans, and
rich turn logs. Use the python engine when testing LLM pilot prompts.

Player (index 0) strategy — greedy heuristic or LLM pilot when field_notes set:
  * Auto-mulligan using land-count heuristics, then keep.
  * Play a land on the first opportunity each turn.
  * Cast affordable spells (LLM-guided when pilot prompt configured).
  * Attack with every eligible creature each turn.

Opponent (index 1) strategy — archetype-aware:
  * Auto-mulligan opening hand using land-count heuristics.
  * Uses ``InteractiveGame._opponent_main_phase`` with LLM pilot when configured.
  * Attacks with all eligible creatures each turn.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

from deck_registry import CardInfo
from engine.game.interactive import InteractiveGame
from engine.game.session import _GameConfig, create_game
from forge_adapter import SimResult, SimResultLife, SimResultMulligans, SimResultOutcome
from game_log_emitter import (
    build_interactive_game_log,
    emit_interactive_log,
)

logger = logging.getLogger(__name__)

_MAX_TURNS: int = 30


@dataclass(frozen=True)
class _HeadlessConfig:
    """Pilot prompts and display names for a headless simulation."""

    names: tuple[str, str]
    on_the_play: bool
    opponent_pilot_prompt: str = ""
    player_pilot_prompt: str = ""
    game_index: int = 0


@dataclass(frozen=True)
class _BatchConfig:
    """Shared matchup settings for a multi-game simulation run."""

    names: tuple[str, str]
    opponent_pilot_prompt: str = ""
    player_pilot_prompt: str = ""


def _run_player_turn(game: InteractiveGame) -> None:
    """Drive one full player turn: draw, main1, combat, main2, end."""
    if game.phase == "draw":
        game.action_draw()

    if game.phase == "main1":
        game.action_auto_main()
        if game.phase == "game_over":
            return
        game.action_go_to_attack()

    if game.phase == "attack":
        game.action_auto_attack()
        if game.phase == "game_over":
            return

    if game.phase == "main2":
        game.action_auto_main()
        if game.phase == "game_over":
            return
        game.action_end_turn()


def run_one_game(
    player_cards: list[CardInfo],
    opponent_cards: list[CardInfo],
    config: _HeadlessConfig,
) -> SimResult:
    """Create and drive a single headless game to completion."""
    player_name, opponent_name = config.names
    game: InteractiveGame = create_game(
        player_cards,
        opponent_cards,
        _GameConfig(
            player_name=player_name,
            opponent_name=opponent_name,
            on_the_play=config.on_the_play,
            pilot_prompt=config.opponent_pilot_prompt,
            player_pilot_prompt=config.player_pilot_prompt,
        ),
    )
    opp_mulls = game.auto_opponent_opening_mulligan()
    opening_hand = game.auto_player_opening_mulligan_then_keep()

    while game.phase != "game_over":
        if game.turn > _MAX_TURNS:
            break
        phase = game.phase
        if phase in ("draw", "main1", "attack", "main2"):
            _run_player_turn(game)
        elif phase == "declare_blockers":
            game.action_confirm_blocks()
        else:
            break

    timed_out = game.phase != "game_over"
    winner = game.winner
    if winner is None:
        winner = random.randint(0, 1)

    if config.game_index < 3:
        emit_interactive_log(game, player_name, opponent_name, config.game_index)

    game_log = build_interactive_game_log(
        game,
        config.game_index,
        config.on_the_play,
        opp_mulls,
        opening_hand,
    )

    return SimResult(
        outcome=SimResultOutcome(winner=winner, timed_out=timed_out),
        turns=game.turn,
        life=SimResultLife(
            player=game.state.players[0].life,
            opponent=game.state.players[1].life,
        ),
        on_the_play=config.on_the_play,
        mulligans=SimResultMulligans(
            player=game.mulligans_taken,
            opponent=opp_mulls,
        ),
        log=game_log,
    )


def run_simulation(
    player_cards: list[CardInfo],
    opponent_cards: list[CardInfo],
    n_games: int,
    batch: _BatchConfig,
) -> list[SimResult]:
    """Run ``n_games`` headless games and return all results."""
    results: list[SimResult] = []
    for i in range(n_games):
        on_the_play = i % 2 == 0
        try:
            result = run_one_game(
                player_cards,
                opponent_cards,
                _HeadlessConfig(
                    names=batch.names,
                    on_the_play=on_the_play,
                    opponent_pilot_prompt=batch.opponent_pilot_prompt,
                    player_pilot_prompt=batch.player_pilot_prompt,
                    game_index=i,
                ),
            )
            results.append(result)
        except RuntimeError as exc:
            logger.warning("Game %d raised RuntimeError, skipping: %s", i, exc)
        except AssertionError as exc:
            logger.warning("Game %d assertion failed, skipping: %s", i, exc)
    return results
