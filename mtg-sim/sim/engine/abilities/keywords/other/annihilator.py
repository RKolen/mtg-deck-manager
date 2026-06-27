"""Annihilator: on attack, destroy defending player's permanents."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_ANNIHILATOR_RE = re.compile(r'annihilator\s+(\w+|\d+)', re.IGNORECASE)


def has_annihilator(perm: Permanent) -> bool:
    """Return True when the permanent has annihilator."""
    return has_keyword(perm, 'Annihilator')


def has_annihilator_card(card: CardInfo) -> bool:
    """Return True when the card has annihilator."""
    return has_registered_keyword(card.oracle_text, 'Annihilator')


def annihilator_amount(oracle_text: str) -> int:
    """Parse N from 'Annihilator N' (default 1)."""
    match = _ANNIHILATOR_RE.search(oracle_text)
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_annihilator_on_attack(game: GameState, attacker: Permanent) -> str | None:
    """Destroy up to N permanents the defending player controls (simplified)."""
    if not has_annihilator(attacker):
        return None
    amount = annihilator_amount(attacker.oracle_text)
    defender = 1 - attacker.controller_idx
    victims = [
        perm
        for perm in list(game.zones.battlefield)
        if perm.controller_idx == defender
    ]
    destroyed = 0
    for perm in victims[:amount]:
        game.zones.leave_battlefield(perm, Zone.GRAVEYARD, 'annihilator', game)
        destroyed += 1
    if destroyed == 0:
        return None
    return f"annihilator destroyed {destroyed} permanent(s)"
