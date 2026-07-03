"""Per-card effect scripts (Phase G).

Scripts are keyed by card name. Unscripted cards fall back to oracle regex handlers.
"""

from __future__ import annotations

from engine.cards.effects import CardEffect, DealDamageToPlayer, Mill

# Owned-deck and archetype scripts are added here incrementally.
CARD_SCRIPTS: dict[str, tuple[CardEffect, ...]] = {
    # Simplified Mind Funeral: mill four (discard/reveal omitted for now).
    'Mind Funeral': (Mill(count=4, target='target_player'),),
    # Proof-of-concept burn script for integration tests.
    'Scripted Shock': (DealDamageToPlayer(amount=2, target='opponent'),),
}
