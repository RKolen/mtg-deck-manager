"""Counter and replacement keywords: Infect, Wither, Persist, Undying, Modular."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent


def has_infect(perm: Permanent) -> bool:
    """Return True when combat damage gives poison or -1/-1 counters."""
    return has_keyword(perm, 'Infect')


def has_wither(perm: Permanent) -> bool:
    """Return True when damage to creatures gives -1/-1 counters."""
    return has_keyword(perm, 'Wither')


def has_persist(perm: Permanent) -> bool:
    """Return True when the creature returns with -1/-1 if it had none."""
    return has_keyword(perm, 'Persist')


def has_undying(perm: Permanent) -> bool:
    """Return True when the creature returns with +1/+1 if it had none."""
    return has_keyword(perm, 'Undying')


def has_modular(perm: Permanent) -> bool:
    """Return True when the permanent has modular."""
    return has_keyword(perm, 'Modular')


def is_indestructible(perm: Permanent) -> bool:
    """Return True when lethal damage and destroy effects do not destroy this permanent."""
    return has_keyword(perm, 'Indestructible')
