"""
ForgeAdapter — runs MTG simulations via a local Forge JAR subprocess.

FORGE_JAR must point to the built forge-gui-desktop JAR. The adapter writes
temporary .dck files and invokes Forge's built-in 'sim' command. Forge handles
full MTG rules; we parse its stdout for results.

Deck format (.dck):
  [metadata]
  Name=DeckName
  [Main]
  4 Card Name
  [Sideboard]
  2 Sideboard Card
"""

from __future__ import annotations

import logging
import os
import pathlib
import re
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from _sim_types import SimResult
from forge_verbose_parser import _parse_forge_verbose_output
from forge_pilot import (
    ForgePilotConfig,
    ForgeRunBudget,
    ForgeSimOptions,
    build_forge_cmd,
    deck_ai_hints,
    forge_pilot_mode_for_archetype,
    forge_run_budget,
    invoke_forge,
)
from game_log_emitter import emit_batch_game_logs
from sim_batch import run_chunked_simulation

if TYPE_CHECKING:
    from deck_registry import CardInfo

logger = logging.getLogger(__name__)

FORGE_JAR: str = os.environ.get("FORGE_JAR", "")


def forge_jar_available() -> bool:
    """Return True when FORGE_JAR points to an existing file."""
    return bool(FORGE_JAR and os.path.isfile(FORGE_JAR))


# ---------------------------------------------------------------------------
# .dck export
# ---------------------------------------------------------------------------

def _write_dck(
    cards: list["CardInfo"],
    name: str,
    path: pathlib.Path,
    ai_hints_line: Optional[str] = None,
) -> None:
    """Write a list of CardInfo objects as a Forge .dck file."""
    lines = ["[metadata]", f"Name={name}"]
    if ai_hints_line:
        lines.append(ai_hints_line)
    lines.append("[Main]")
    for c in cards:
        if not c.sideboard:
            lines.append(f"{c.quantity} {c.name}")
    sideboard = [c for c in cards if c.sideboard]
    if sideboard:
        lines.append("[Sideboard]")
        for c in sideboard:
            lines.append(f"{c.quantity} {c.name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


_FORGE_DECK_DIR = pathlib.Path.home() / ".forge" / "decks" / "constructed"


def _log_forge_run(
    player_name: str,
    opponent_name: str,
    n_games: int,
    pilot_cfg: ForgePilotConfig,
    budget: ForgeRunBudget,
) -> None:
    """Log whether this batch uses LLM pilot or built-in AI."""
    if pilot_cfg.pilot_active():
        logger.info(
            "Running Forge: %s vs %s, %d games — LLM pilot "
            "(player %d chars, opponent %d chars) via %s "
            "(pilot %ds/call, match clock %ds, subprocess %ds)",
            player_name,
            opponent_name,
            n_games,
            len(pilot_cfg.player_pilot_prompt.strip()),
            len(pilot_cfg.opponent_pilot_prompt.strip()),
            pilot_cfg.pilot_url,
            pilot_cfg.pilot_timeout,
            budget.clock,
            budget.subprocess_timeout,
        )
        return
    logger.info(
        "Running Forge: %s vs %s, %d games — Forge built-in AI only "
        "(match clock %ds, subprocess %ds)",
        player_name, opponent_name, n_games,
        budget.clock, budget.subprocess_timeout,
    )


def _forge_file_slug(display_name: str, run_id: str, fallback: str) -> str:
    """Build a unique Forge .dck filename stem from a human deck title."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", display_name).strip("_")[:48]
    return f"{slug or fallback}_{run_id}"


@dataclass(frozen=True)
class ForgeDeckNames:
    """Human-readable deck titles written into Forge .dck metadata."""

    player: str
    opponent: str


def _materialize_forge_decks(
    player_cards: list["CardInfo"],
    opponent_cards: list["CardInfo"],
    pilot_cfg: ForgePilotConfig,
    run_id: str,
    deck_names: ForgeDeckNames,
) -> tuple[str, str, pathlib.Path, pathlib.Path]:
    """Write temporary .dck files and return deck file stems and paths."""
    combo_mode = forge_pilot_mode_for_archetype(pilot_cfg.opponent_archetype)
    p_slug = _forge_file_slug(deck_names.player, run_id, "player")
    o_slug = _forge_file_slug(deck_names.opponent, run_id, "opponent")
    p_dck = _FORGE_DECK_DIR / f"{p_slug}.dck"
    o_dck = _FORGE_DECK_DIR / f"{o_slug}.dck"
    p_hints = deck_ai_hints(pilot_cfg.player_pilot_prompt)
    o_hints = deck_ai_hints(
        pilot_cfg.opponent_pilot_prompt,
        combo_mode,
    )
    _write_dck(player_cards, deck_names.player, p_dck, p_hints)
    _write_dck(opponent_cards, deck_names.opponent, o_dck, o_hints)
    return p_slug, o_slug, p_dck, o_dck


def run_forge_batch(
    player_cards: list["CardInfo"],
    opponent_cards: list["CardInfo"],
    n_games: int,
    *,
    deck_names: tuple[str, str] = ("Player", "Opponent"),
    pilot: Optional[ForgePilotConfig] = None,
) -> list[SimResult]:
    """
    Run n_games via Forge's built-in sim command.

    Writes temporary .dck files into ~/.forge/decks/constructed/ (where Forge's
    deckFromCommandLineParameter expects them), invokes the JAR as a subprocess,
    and parses stdout for per-game winners.
    """
    player_name, opponent_name = deck_names
    pilot_cfg = pilot or ForgePilotConfig()
    _FORGE_DECK_DIR.mkdir(parents=True, exist_ok=True)
    p_slug, o_slug, p_dck, o_dck = _materialize_forge_decks(
        player_cards, opponent_cards, pilot_cfg, uuid.uuid4().hex[:8],
        ForgeDeckNames(player=player_name, opponent=opponent_name),
    )
    budget = forge_run_budget(n_games, pilot_cfg)

    try:
        _log_forge_run(player_name, opponent_name, n_games, pilot_cfg, budget)
        stdout = invoke_forge(
            build_forge_cmd(p_slug, o_slug, n_games, pilot_cfg),
            n_games,
            budget.subprocess_timeout,
        )
        if not stdout:
            return []

        results = _parse_forge_verbose_output(stdout, player_name)
        if not results:
            logger.warning(
                "Forge produced no parseable results.\nstdout: %s", stdout[:1000]
            )
        return results
    finally:
        p_dck.unlink(missing_ok=True)
        o_dck.unlink(missing_ok=True)


class ForgeAdapter:
    """Run batch simulations through a local Forge JAR."""

    def __init__(self) -> None:
        """Require FORGE_JAR to point at an existing desktop JAR."""
        if not forge_jar_available():
            raise RuntimeError(
                "FORGE_JAR is not set or the file does not exist. "
                "Point it at the Forge desktop JAR."
            )
        logger.info("ForgeAdapter FORGE mode — JAR: %s", FORGE_JAR)

    def run_simulation(
        self,
        player_cards: list["CardInfo"],
        opponent_cards: list["CardInfo"],
        n_games: int,
        *,
        options: Optional[ForgeSimOptions] = None,
    ) -> list[SimResult]:
        """Run n_games via Forge and return one SimResult per game."""
        opts = options or ForgeSimOptions()
        player_name, opponent_name = opts.deck_names

        def after_batch(batch: list[SimResult]) -> None:
            emit_batch_game_logs(batch, player_name, opponent_name)

        results = run_chunked_simulation(
            n_games,
            lambda chunk, _start: run_forge_batch(
                player_cards,
                opponent_cards,
                chunk,
                deck_names=opts.deck_names,
                pilot=opts.pilot,
            ),
            label=f"{player_name} vs {opponent_name}",
            after_batch=after_batch,
        )
        return results

    def close(self) -> None:
        """No-op; provided for interface symmetry."""
