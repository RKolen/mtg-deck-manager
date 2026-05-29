"""Augment: ETB merge onto a host creature instead of staying on the battlefield."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.abilities.keywords.other.host_creature import find_host_creature
from engine.core.game_object import CardObject, Permanent
from engine.core.zones import ZoneManager


def has_augment(perm: Permanent) -> bool:
    """Return True when the permanent has augment."""
    return has_keyword(perm, 'Augment')


def _augment_stats(permanent: Permanent) -> tuple[int, int]:
    info = permanent.card_info
    if info is None:
        return 0, 0
    return max(0, info.numeric_power), max(0, info.numeric_toughness)


def apply_augment_etb(
    zones: ZoneManager,
    permanent: Permanent,
    battlefield: list[Permanent],
) -> str | None:
    """Put augment stats on a host creature and remove the augment card from play."""
    if not has_augment(permanent):
        return None
    power, toughness = _augment_stats(permanent)
    if power == 0 and toughness == 0:
        return None
    host = find_host_creature(
        permanent,
        battlefield,
        exclude=has_augment,
    )
    if host is None:
        return None
    amount = max(power, toughness)
    put_plus_counters(host, amount)
    if permanent in zones.battlefield and isinstance(permanent.source, CardObject):
        zones.battlefield.remove(permanent)
        zones.player_zones[permanent.controller_idx].exile.append(permanent.source)
    return f"augment +{amount}/+{amount} on {host.name}"
