"""Built-in card effect templates copied into per-deck cache on sync (Phase G).

These are generic public card definitions, not tied to any user's deck list.
"""

from __future__ import annotations

from engine.cards.effects import (
    CardEffect,
    DealDamage,
    DestroyIfMaxManaValue,
    DestroyPermanent,
    DiscardCards,
    DrainLife,
    DrawCards,
    ExilePermanent,
    Mill,
    Modal,
    PumpUntilEOT,
    Scry,
    SetPowerToughnessUntilEOT,
    TreasureHunt,
)

BUILTIN_CARD_SCRIPTS: dict[str, tuple[CardEffect, ...]] = {
    'Become Immense': (PumpUntilEOT(power=6, toughness=6),),
    'Collective Brutality': (
        Modal(modes=(
            DiscardCards(count=1, target='target_player'),
            PumpUntilEOT(power=-2, toughness=-2),
            DrainLife(amount=2),
        )),
    ),
    'Doom Blade': (DestroyPermanent(),),
    'Fatal Push': (DestroyIfMaxManaValue(max_mv=2),),
    'Gitaxian Probe': (DrawCards(count=1),),
    'Glimpse the Unthinkable': (Mill(count=10, target='target_player'),),
    'Go for the Throat': (DestroyPermanent(),),
    'Hagra Mauling // Hagra Broodpit': (DestroyPermanent(),),
    'Lightning Bolt': (DealDamage(amount=3),),
    'Molten Collapse': (
        Modal(modes=(
            DestroyPermanent(),
            DealDamage(amount=3),
        )),
    ),
    'Murder': (DestroyPermanent(),),
    'Mutagenic Growth': (PumpUntilEOT(power=2, toughness=2),),
    'Path to Exile': (ExilePermanent(),),
    "Prey's Vengeance": (PumpUntilEOT(power=2, toughness=2),),
    'Requiting Hex': (DestroyIfMaxManaValue(max_mv=2),),
    'Scale Up': (SetPowerToughnessUntilEOT(power=6, toughness=4),),
    'Serum Visions': (Scry(count=2), DrawCards(count=1)),
    'Shock': (DealDamage(amount=2),),
    'Sleight of Hand': (DrawCards(count=1),),
    'Thoughtseize': (DiscardCards(count=1, target='target_player'),),
    'Treasure Hunt': (TreasureHunt(),),
    'Unholy Heat': (DealDamage(amount=2),),
}
