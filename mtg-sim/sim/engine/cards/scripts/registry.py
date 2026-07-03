"""Per-card effect scripts (Phase G).

Scripts are keyed by card name. Unscripted cards fall back to oracle regex handlers.
"""

from __future__ import annotations

from engine.cards.effects import CardEffect, Mill
from engine.cards.scripts.staples import STAPLE_SCRIPTS

# Owned-deck scripts are merged here as they are authored.
_OWNED_DECK_SCRIPTS: dict[str, tuple[CardEffect, ...]] = {
    # Simplified Mind Funeral: mill four (discard/reveal omitted for now).
    'Mind Funeral': (Mill(count=4, target='target_player'),),
}

CARD_SCRIPTS: dict[str, tuple[CardEffect, ...]] = {
    **_OWNED_DECK_SCRIPTS,
    **STAPLE_SCRIPTS,
}
