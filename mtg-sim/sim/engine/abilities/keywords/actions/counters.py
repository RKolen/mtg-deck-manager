"""Counter-manipulation keyword actions: Proliferate, Bolster, Support, Counter."""

from __future__ import annotations

import re

from engine.abilities.keywords.actions._parse import parse_amount_after_keyword, word_to_int
from engine.abilities.keywords.actions.detect import has_keyword_action
from engine.core.game_object import Permanent
from engine.core.zones import ZoneManager

if True:
    from engine.core.game_state import GameState

_BOLSTER_RE = re.compile(
    r'bolster (\w+|\d+)',
    re.IGNORECASE,
)
_SUPPORT_RE = re.compile(
    r'support (\w+|\d+)',
    re.IGNORECASE,
)
_COUNTER_ACTION_RE = re.compile(
    r'put (\w+|\d+) \+1/\+1 counter',
    re.IGNORECASE,
)


def has_proliferate(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Proliferate action."""
    return has_keyword_action(oracle_text, 'Proliferate')


def has_bolster(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Bolster action."""
    return has_keyword_action(oracle_text, 'Bolster')


def has_support(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Support action."""
    return has_keyword_action(oracle_text, 'Support')


def has_counter_action(oracle_text: str | None) -> bool:
    """Return True when oracle uses Counter as a +1/+1 counter action (not spell counter)."""
    if not has_keyword_action(oracle_text, 'Counter'):
        return False
    return bool(_COUNTER_ACTION_RE.search(oracle_text or ''))


def bolster_amount(oracle_text: str) -> int:
    """Parse N from 'Bolster N'."""
    match = _BOLSTER_RE.search(oracle_text)
    if match is None:
        return parse_amount_after_keyword(oracle_text, 'bolster')
    return word_to_int(match.group(1))


def support_amount(oracle_text: str) -> int:
    """Parse N from 'Support N'."""
    match = _SUPPORT_RE.search(oracle_text)
    if match is None:
        return 1
    return word_to_int(match.group(1))


def counter_action_amount(oracle_text: str) -> int:
    """Parse how many +1/+1 counters the Counter action places."""
    match = _COUNTER_ACTION_RE.search(oracle_text)
    if match is None:
        return 1
    return word_to_int(match.group(1))


def put_plus_counters(perm: Permanent, count: int) -> None:
    """Add +1/+1 counters to a permanent."""
    if count <= 0:
        return
    perm.counters['+1/+1'] = perm.counters.get('+1/+1', 0) + count


def proliferate(game: GameState) -> list[str]:
    """Give one of each counter type to each permanent and player that has that type."""
    details: list[str] = []
    for player in game.players:
        if player.poison > 0:
            player.poison += 1
            details.append(f"{player.name} poison → {player.poison}")
    for perm in game.zones.battlefield:
        for counter_type, amount in list(perm.counters.items()):
            if amount > 0:
                perm.counters[counter_type] = amount + 1
                details.append(f"{perm.name} {counter_type} → {perm.counters[counter_type]}")
    return details


def bolster_lowest_creature(zones: ZoneManager, controller_idx: int, amount: int) -> str | None:
    """Bolster N on the lowest-toughness creature you control (MVP)."""
    creatures = [
        p for p in zones.permanents_of(controller_idx)
        if 'Creature' in p.type_line
    ]
    if not creatures:
        return None

    def toughness(perm: Permanent) -> int:
        if perm.card_info is not None:
            base = perm.card_info.numeric_toughness
        else:
            base = 0
        return base + perm.counters.get('+1/+1', 0) - perm.counters.get('-1/-1', 0)

    target = min(creatures, key=toughness)
    put_plus_counters(target, amount)
    return target.name


def support_creatures(
    zones: ZoneManager,
    controller_idx: int,
    amount: int,
    target_uid: str | None,
) -> str | None:
    """Support N: put N +1/+1 counters on target creature (or last creature)."""
    target = None
    if target_uid is not None:
        try:
            target = zones.find_permanent(int(target_uid))
        except ValueError:
            target = None
    if target is None:
        creatures = [
            p for p in zones.permanents_of(controller_idx)
            if 'Creature' in p.type_line
        ]
        target = creatures[-1] if creatures else None
    if target is None:
        return None
    put_plus_counters(target, amount)
    return target.name
