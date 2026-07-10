"""Built-in card effect templates copied into per-deck cache on sync (Phase G).

These are generic public card definitions, not tied to any user's deck list.
"""

from __future__ import annotations

from engine.cards.effects import (
    CardEffect,
    DealDamage,
    DeliriumDealDamage,
    DestroyIfMaxManaValue,
    DestroyPermanent,
    DiscardCards,
    DrainLife,
    DrawCards,
    ExilePermanent,
    GainLife,
    Mill,
    Modal,
    PumpUntilEOT,
    Scry,
    SetPowerToughnessUntilEOT,
    Surveil,
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
    'Consider': (Scry(count=1), Surveil(count=1)),
    'Electrolyze': (DealDamage(amount=2), DrawCards(count=1)),
    'Faithless Looting': (DrawCards(count=2), DiscardCards(count=2, target='controller')),
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
    'Opt': (Scry(count=1), DrawCards(count=1)),
    'Path to Exile': (ExilePermanent(),),
    "Prey's Vengeance": (PumpUntilEOT(power=2, toughness=2),),
    'Requiting Hex': (DestroyIfMaxManaValue(max_mv=2),),
    'Scale Up': (SetPowerToughnessUntilEOT(power=6, toughness=4),),
    'Serum Visions': (Scry(count=2), DrawCards(count=1)),
    'Shock': (DealDamage(amount=2),),
    'Sleight of Hand': (DrawCards(count=1),),
    'Thoughtseize': (DiscardCards(count=1, target='target_player'),),
    'Treasure Hunt': (TreasureHunt(),),
    'Unholy Heat': (DeliriumDealDamage(base_amount=2, delirium_amount=6),),
    'Swords to Plowshares': (ExilePermanent(),),
    'Terminate': (DestroyPermanent(),),
    'Thought Scour': (Mill(count=2, target='target_player'),),
    'Weather the Storm': (GainLife(amount=3),),
}
