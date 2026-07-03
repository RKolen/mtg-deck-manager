"""Load and resolve per-card effect scripts (Phase G)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.cards.builtin_scripts import BUILTIN_CARD_SCRIPTS
from engine.cards.effects import CardEffectContext, EffectList

if TYPE_CHECKING:
    from deck_registry import CardInfo
    from engine.cards.effects import CardEffect
    from engine.core.game_state import GameState


def _active_scripts(game: GameState | None) -> dict[str, tuple[CardEffect, ...]]:
    if game is not None and game.card_scripts:
        return game.card_scripts
    return BUILTIN_CARD_SCRIPTS


def has_script(card: CardInfo, game: GameState | None = None) -> bool:
    """Return True when a structured script exists for this card name."""
    return card.name in _active_scripts(game)


def scripted_effects_for(
    card: CardInfo,
    game: GameState | None = None,
) -> tuple[CardEffect, ...] | None:
    """Return scripted effects for a card, or None when unscripted."""
    return _active_scripts(game).get(card.name)


def scripted_card_names(game: GameState | None = None) -> frozenset[str]:
    """Return all card names that have structured scripts in the active set."""
    return frozenset(_active_scripts(game))


def resolve_scripted_spell(ctx: CardEffectContext) -> str | None:
    """Apply a card script when one exists; otherwise return None for regex fallback."""
    card_info = ctx.source.card_info
    if card_info is None:
        return None
    effects = scripted_effects_for(card_info, ctx.game)
    if effects is None:
        return None
    return EffectList(effects).apply(ctx)
