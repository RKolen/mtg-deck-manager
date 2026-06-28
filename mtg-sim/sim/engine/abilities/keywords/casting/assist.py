"""Assist: other players may pay mana toward this spell's cost (CR 702.132, simplified)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword


def has_assist(card: CardInfo) -> bool:
    """Return True when the card has assist."""
    return has_registered_keyword(card.oracle_text, 'Assist')


def has_assist_card(card: CardInfo) -> bool:
    """Return True when the card has assist."""
    return has_assist(card)


def resolve_assist_for_cast(
    card: CardInfo,
    mana_needed: int,
    assist_mana: int,
) -> tuple[int, int, str | None]:
    """Apply assist reduction; return remaining mana, applied assist, and errors."""
    if assist_mana <= 0:
        return mana_needed, 0, None
    if not has_assist(card):
        return mana_needed, 0, f"{card.name} does not have assist"
    applied = min(mana_needed, assist_mana)
    return mana_needed - applied, applied, None
