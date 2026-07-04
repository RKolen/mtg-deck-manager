"""Load and resolve per-card effect scripts (Phase G)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.cards.builtin_scripts import BUILTIN_CARD_SCRIPTS
from engine.cards.effects import CardEffectContext, EffectList

if TYPE_CHECKING:
    from deck_registry import CardInfo
    from engine.cards.effects import CardEffect
    from engine.core.game_state import GameState


def _per_game_scripts(game: GameState | None) -> dict[str, tuple[CardEffect, ...]]:
    if game is None:
        return {}
    return game.card_scripts


def has_script(card: CardInfo, game: GameState | None = None) -> bool:
    """Return True when a structured script exists for this card name."""
    return scripted_effects_for(card, game) is not None


def scripted_effects_for(
    card: CardInfo,
    game: GameState | None = None,
) -> tuple[CardEffect, ...] | None:
    """Return scripted effects: per-game cache first, then built-in templates."""
    per_game = _per_game_scripts(game)
    effects = per_game.get(card.name)
    if effects is not None:
        return effects
    return BUILTIN_CARD_SCRIPTS.get(card.name)


def scripted_card_names(game: GameState | None = None) -> frozenset[str]:
    """Return card names with scripts in the active per-game set plus builtins."""
    names = set(BUILTIN_CARD_SCRIPTS)
    names.update(_per_game_scripts(game))
    return frozenset(names)


def resolve_scripted_spell(ctx: CardEffectContext) -> str | None:
    """Apply a card script when one exists; otherwise return None for regex fallback."""
    card_info = ctx.source.card_info
    if card_info is None:
        return None
    effects = scripted_effects_for(card_info, ctx.game)
    if effects is None:
        return None
    return EffectList(effects).apply(ctx)
