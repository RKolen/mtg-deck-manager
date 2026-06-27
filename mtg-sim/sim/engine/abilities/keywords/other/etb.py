"""Apply ability_other ETB hooks when a permanent enters the battlefield."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords.other.register import register_permanent_other_keywords
from engine.abilities.keywords.ability_words.register import (
    register_permanent_ability_words,
)
from engine.abilities.keywords.other.etb_handlers import ETB_DETAIL_PRODUCERS
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def apply_etb_other_abilities(game: GameState, permanent: Permanent) -> list[str]:
    """Run wired ability_other ETB effects; return log fragments."""
    register_permanent_other_keywords(permanent, game.trigger_registry)
    register_permanent_ability_words(permanent, game.trigger_registry)
    return [
        detail
        for producer in ETB_DETAIL_PRODUCERS
        if (detail := producer(game, permanent))
    ]
