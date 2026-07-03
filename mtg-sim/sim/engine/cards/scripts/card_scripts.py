"""Per-card effect scripts (Phase G).

Keyed by card name. Unscripted cards fall back to oracle regex handlers.
Add entries as individual cards need structured resolution.
"""

from __future__ import annotations

from engine.cards.effects import (
    CardEffect,
    DealDamage,
    DestroyIfMaxManaValue,
    DestroyPermanent,
    DrainLife,
    DrawCards,
    ExilePermanent,
    Mill,
    Modal,
    NoEffect,
    PumpUntilEOT,
    SetPowerToughnessUntilEOT,
    TreasureHunt,
)

CARD_SCRIPTS: dict[str, tuple[CardEffect, ...]] = {
    'Become Immense': (PumpUntilEOT(power=6, toughness=6),),
    'Collective Brutality': (
        Modal(modes=(
            NoEffect(label='discard'),
            PumpUntilEOT(power=-2, toughness=-2),
            DrainLife(amount=2),
        )),
    ),
    'Doom Blade': (DestroyPermanent(),),
    'Fatal Push': (DestroyPermanent(),),
    'Gitaxian Probe': (DrawCards(count=1),),
    'Glimpse the Unthinkable': (Mill(count=10, target='target_player'),),
    'Go for the Throat': (DestroyPermanent(),),
    'Hagra Mauling // Hagra Broodpit': (DestroyPermanent(),),
    'Lightning Bolt': (DealDamage(amount=3),),
    'Murder': (DestroyPermanent(),),
    'Mutagenic Growth': (PumpUntilEOT(power=2, toughness=2),),
    'Path to Exile': (ExilePermanent(),),
    "Prey's Vengeance": (PumpUntilEOT(power=2, toughness=2),),
    'Requiting Hex': (DestroyIfMaxManaValue(max_mv=2),),
    'Scale Up': (SetPowerToughnessUntilEOT(power=6, toughness=4),),
    'Treasure Hunt': (TreasureHunt(),),
}
