"""Scripts for common Modern and Commander staples (Phase G)."""

from __future__ import annotations

from engine.cards.effects import (
    CardEffect,
    DealDamage,
    DestroyPermanent,
    ExilePermanent,
    Mill,
)

STAPLE_SCRIPTS: dict[str, tuple[CardEffect, ...]] = {
    'Lightning Bolt': (DealDamage(amount=3),),
    'Path to Exile': (ExilePermanent(),),
    'Fatal Push': (DestroyPermanent(),),
    'Doom Blade': (DestroyPermanent(),),
    'Murder': (DestroyPermanent(),),
    'Go for the Throat': (DestroyPermanent(),),
    'Glimpse the Unthinkable': (Mill(count=10, target='target_player'),),
}
