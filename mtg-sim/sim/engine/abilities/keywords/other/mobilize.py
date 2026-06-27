"""Mobilize: create Soldier tokens when this creature attacks."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords._token_factory import enter_token_from_blueprint
from engine.cards.oracle_parse import TokenBlueprint
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_MOBILIZE_RE = re.compile(r'mobilize\s+(\w+|\d+)', re.IGNORECASE)

_SOLDIER = TokenBlueprint(
    name='Soldier',
    type_line='Creature — Soldier',
    power='1',
    toughness='1',
    colors=[],
    oracle_text='',
)


def has_mobilize(perm: Permanent) -> bool:
    """Return True when the permanent has mobilize."""
    return has_keyword(perm, 'Mobilize')


def has_mobilize_card(card: CardInfo) -> bool:
    """Return True when the card has mobilize."""
    return has_registered_keyword(card.oracle_text, 'Mobilize')


def mobilize_amount(oracle_text: str) -> int:
    """Parse N from 'Mobilize N' (default 1)."""
    match = _MOBILIZE_RE.search(oracle_text)
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_mobilize_on_attack(
    game: GameState,
    attacker: Permanent,
) -> str | None:
    """Create N 1/1 Soldier tokens when this creature attacks."""
    if not has_mobilize(attacker):
        return None
    amount = mobilize_amount(attacker.oracle_text)
    for _ in range(amount):
        enter_token_from_blueprint(
            game.zones,
            attacker.controller_idx,
            _SOLDIER,
            cause='mobilize',
        )
    return f"mobilize {amount} Soldier token(s) for {attacker.name}"
