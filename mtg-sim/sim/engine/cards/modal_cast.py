"""Choose-one mode selection for scripted Modal effects (Phase G)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.cards.effects import CardEffect, EffectList, Modal
from engine.cards.oracle_infer import infer_effects_from_oracle
from engine.cards.script_loader import scripted_effects_for

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def _modal_from_effects(effects: tuple[CardEffect, ...] | None) -> Modal | None:
    if effects is None:
        return None
    for effect in effects:
        if isinstance(effect, Modal):
            return effect
        if isinstance(effect, EffectList):
            nested = _modal_from_effects(effect.effects)
            if nested is not None:
                return nested
    return None


def scripted_modal_mode_count(
    card: CardInfo,
    game: GameState | None = None,
) -> int | None:
    """Return the number of scripted modal modes, or None when not modal."""
    effects = scripted_effects_for(card, game)
    modal = _modal_from_effects(effects)
    if modal is not None:
        return len(modal.modes)
    inferred = infer_effects_from_oracle(card)
    modal = _modal_from_effects(inferred)
    if modal is not None:
        return len(modal.modes)
    return None


def normalize_scripted_modal_mode(
    card: CardInfo,
    mode_index: int | None,
    game: GameState | None = None,
) -> int | None:
    """Return a legal scripted modal index, or None when not used."""
    if mode_index is None:
        return None
    count = scripted_modal_mode_count(card, game)
    if count is None or not 0 <= mode_index < count:
        return None
    return mode_index


def modal_selection_error(
    card: CardInfo,
    mode_index: int | None,
    game: GameState | None = None,
) -> str | None:
    """Return an error when a scripted modal mode choice is illegal."""
    if mode_index is None:
        return None
    if scripted_modal_mode_count(card, game) is None:
        return f"{card.name} has no scripted modal modes"
    if normalize_scripted_modal_mode(card, mode_index, game) is None:
        return "Choose one: invalid mode index"
    return None
