"""Amass keyword action."""

from __future__ import annotations

import re

from engine.abilities.keywords.actions._parse import parse_amount_after_keyword, word_to_int
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.abilities.keywords.actions.detect import has_keyword_action
from engine.abilities.keywords._token_factory import enter_token_from_blueprint
from engine.cards.oracle_parse import TokenBlueprint
from engine.core.game_object import Permanent
from engine.core.zones import ZoneManager

_AMASS_RE = re.compile(r'\bamass (\w+|\d+)', re.IGNORECASE)


def has_amass(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Amass action."""
    return has_keyword_action(oracle_text, 'Amass')


def amass_amount(oracle_text: str) -> int:
    """Parse N from 'Amass N'."""
    match = _AMASS_RE.search(oracle_text)
    if match is not None:
        return word_to_int(match.group(1))
    return parse_amount_after_keyword(oracle_text, 'amass')


def army_token_blueprint() -> TokenBlueprint:
    """Standard Army token for Amass."""
    return TokenBlueprint(
        name='Army Token',
        type_line='Creature — Army',
        power='0',
        toughness='0',
        colors=[],
        oracle_text='',
    )


def find_army(zones: ZoneManager, controller_idx: int) -> Permanent | None:
    """Return an Army creature the controller already controls, if any."""
    for perm in zones.battlefield:
        if perm.controller_idx == controller_idx and 'Army' in perm.type_line:
            return perm
    return None


def amass_army(zones: ZoneManager, controller_idx: int, oracle_text: str) -> str:
    """Amass N: create Army or add +1/+1 counters to your Army."""
    amount = amass_amount(oracle_text)
    if amount <= 0:
        return ''
    army = find_army(zones, controller_idx)
    if army is not None:
        put_plus_counters(army, amount)
        return f"amassed {amount} on {army.name}"
    enter_token_from_blueprint(
        zones,
        controller_idx,
        army_token_blueprint(),
        cause='amass',
    )
    army = find_army(zones, controller_idx)
    if army is None:
        return f"amassed {amount}"
    put_plus_counters(army, amount)
    return f"created Army and amassed {amount}"
