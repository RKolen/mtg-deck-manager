"""Fabricate: ETB with +1/+1 counters or a Servo artifact token."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords._token_factory import enter_token_from_blueprint
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.cards.oracle_parse import TokenBlueprint
from engine.core.game_object import Permanent
from engine.core.zones import ZoneManager

_FABRICATE_RE = re.compile(r'fabricate\s+(\w+|\d+)', re.IGNORECASE)

_SERVO = TokenBlueprint(
    name='Servo',
    type_line='Artifact Creature — Servo',
    power='1',
    toughness='1',
    colors=[],
    oracle_text='',
)


def has_fabricate(perm: Permanent) -> bool:
    """Return True when the permanent has fabricate."""
    return has_keyword(perm, 'Fabricate')


def has_fabricate_card(card: CardInfo) -> bool:
    """Return True when the card has fabricate."""
    return has_registered_keyword(card.oracle_text, 'Fabricate')


def fabricate_amount(oracle_text: str) -> int:
    """Parse N from 'Fabricate N'."""
    match = _FABRICATE_RE.search(oracle_text)
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_fabricate_etb(
    zones: ZoneManager,
    permanent: Permanent,
) -> str | None:
    """Fabricate: artifact token if oracle mentions artifact, else +1/+1 counters."""
    if not has_fabricate(permanent):
        return None
    amount = fabricate_amount(permanent.oracle_text)
    lowered = permanent.oracle_text.lower()
    if 'artifact token' in lowered or 'create a colorless' in lowered:
        for _ in range(amount):
            enter_token_from_blueprint(
                zones,
                permanent.controller_idx,
                _SERVO,
                cause='fabricate',
            )
        return f"fabricated {amount} Servo(s)"
    put_plus_counters(permanent, amount)
    return f"fabricated +{amount}/+{amount} on {permanent.name}"
