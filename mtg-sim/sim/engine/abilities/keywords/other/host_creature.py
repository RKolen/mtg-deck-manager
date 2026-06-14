"""Shared host-creature lookup for backup, augment, and similar ETB keywords."""

from __future__ import annotations

from collections.abc import Callable

from engine.core.game_object import Permanent


def other_controlled_creatures(
    permanent: Permanent,
    battlefield: list[Permanent],
) -> list[Permanent]:
    """Return other creatures controlled by the same player."""
    return [
        perm
        for perm in battlefield
        if perm.controller_idx == permanent.controller_idx
        and perm.obj_id != permanent.obj_id
        and 'Creature' in perm.type_line
    ]


def find_host_creature(
    permanent: Permanent,
    battlefield: list[Permanent],
    *,
    exclude: Callable[[Permanent], bool] | None = None,
) -> Permanent | None:
    """Return another creature you control to receive backup or augment."""
    reject = exclude or (lambda _perm: False)
    return next(
        (perm for perm in other_controlled_creatures(permanent, battlefield) if not reject(perm)),
        None,
    )
