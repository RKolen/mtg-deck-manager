"""Headless simulation runner using the interactive Python game engine.

Drives both players automatically so that the full game runs without human input.

Player (index 0) strategy — greedy heuristic:
  * Play a land on the first opportunity each turn.
  * Cast all affordable non-land spells cheapest-first (creatures before others).
  * Attack with every eligible creature each turn.
  * Never block (opponent attackers pass through uncontested).

Opponent (index 1) strategy — archetype-aware:
  * Uses ``InteractiveGame._opponent_main_phase`` which calls ``llm_pick`` with
    the pilot prompt when one is configured, giving archetype-specific spell
    selection instead of a generic cheapest-spell heuristic.
  * Attacks with all eligible creatures each turn.

The pilot prompt is fetched from Drupal (``field_pilot_prompt``) by the caller
and passed through to ``create_game``.  When the field is empty the built-in
``_PROMPTS`` dict in ``pilot_prompts.py`` provides the fallback.
"""

from __future__ import annotations

import logging
import random

from deck_registry import CardInfo
from engine.game.interactive import InteractiveGame
from engine.game.session import _GameConfig, create_game
from forge_adapter import SimResult, SimResultLife, SimResultOutcome

logger = logging.getLogger(__name__)

_MAX_TURNS: int = 30


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
    names: tuple[str, str],
    on_the_play: bool,
    pilot_prompt: str = "",
) -> SimResult:
    """Create and drive a single headless game to completion.

    Returns a :class:`~forge_adapter.SimResult` with outcome data.
    Games that exceed ``_MAX_TURNS`` are marked as ``timed_out=True``
    with the winner chosen at random (same behaviour as Forge timeout).
    """
    player_name, opponent_name = names
    game: InteractiveGame = create_game(
        player_cards,
        opponent_cards,
        _GameConfig(
            player_name=player_name,
            opponent_name=opponent_name,
            on_the_play=on_the_play,
            pilot_prompt=pilot_prompt,
        ),
    )
    game.action_keep()

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

    return SimResult(
        outcome=SimResultOutcome(winner=winner, timed_out=timed_out),
        turns=game.turn,
        life=SimResultLife(
            player=game.state.players[0].life,
            opponent=game.state.players[1].life,
        ),
        on_the_play=on_the_play,
    )


def run_simulation(
    player_cards: list[CardInfo],
    opponent_cards: list[CardInfo],
    n_games: int,
    names: tuple[str, str],
    pilot_prompt: str = "",
) -> list[SimResult]:
    """Run ``n_games`` headless games and return all results.

    Games alternate on-the-play / on-the-draw to balance the sample.
    Failed games are logged and skipped so one bad game cannot abort the run.
    """
    results: list[SimResult] = []
    for i in range(n_games):
        on_the_play = i % 2 == 0
        try:
            result = run_one_game(
                player_cards,
                opponent_cards,
                names,
                on_the_play=on_the_play,
                pilot_prompt=pilot_prompt,
            )
            results.append(result)
        except RuntimeError as exc:
            logger.warning("Game %d raised RuntimeError, skipping: %s", i, exc)
        except AssertionError as exc:
            logger.warning("Game %d assertion failed, skipping: %s", i, exc)
    return results
