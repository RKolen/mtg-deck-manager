"""Cipher: encode on instant/sorcery cast (simplified log)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords.ability_words.conditions import is_controller_instant_or_sorcery_cast
from engine.core.game_object import Effect, GameObject, Permanent
from engine.rules.triggers import TriggerDefinition, TriggerEvent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_cipher(perm: Permanent) -> bool:
    """Return True when the permanent has cipher."""
    return has_keyword(perm, 'Cipher')


def has_cipher_card(card: CardInfo) -> bool:
    """Return True when the card has cipher."""
    return has_registered_keyword(card.oracle_text, 'Cipher')


def is_cipher_instant_or_sorcery_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Cipher: you cast an instant or sorcery spell."""
    return is_controller_instant_or_sorcery_cast(event, game, definition)


class CipherEffect(Effect):
    """Log cipher encoding when an instant or sorcery is cast."""

    def __init__(self, clause: str) -> None:
        self.clause = clause

    def resolve(self, game: GameState, source: GameObject) -> str:
        del game, source
        detail = self.clause.strip() or 'encoded'
        return f"cipher: {detail}"
