"""Load and resolve per-card effect scripts (Phase G)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.cards.effects import CardEffectContext, EffectList
from engine.cards.scripts.registry import CARD_SCRIPTS

if TYPE_CHECKING:
    from deck_registry import CardInfo
    from engine.cards.effects import CardEffect


def has_script(card: CardInfo) -> bool:
    """Return True when a structured script exists for this card name."""
    return card.name in CARD_SCRIPTS


def scripted_effects_for(card: CardInfo) -> tuple[CardEffect, ...] | None:
    """Return scripted effects for a card, or None when unscripted."""
    return CARD_SCRIPTS.get(card.name)


def resolve_scripted_spell(ctx: CardEffectContext) -> str | None:
    """Apply a card script when one exists; otherwise return None for regex fallback."""
    card_info = ctx.source.card_info
    if card_info is None:
        return None
    effects = scripted_effects_for(card_info)
    if effects is None:
        return None
    return EffectList(effects).apply(ctx)
