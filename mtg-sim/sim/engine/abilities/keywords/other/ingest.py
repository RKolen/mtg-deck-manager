"""Ingest: defending player exiles top card of library when damaged (simplified)."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent
from engine.core.game_state import GameState


def has_ingest(perm: Permanent) -> bool:
    """Return True when the permanent has ingest."""
    return has_keyword(perm, 'Ingest')


def apply_ingest_on_player_damage(
    game: GameState,
    attacker: Permanent,
    damage: int,
    damaged_player_idx: int,
) -> str | None:
    """Exile the top card of the damaged player's library."""
    if damage <= 0 or not has_ingest(attacker):
        return None
    library = game.zones.player_zones[damaged_player_idx].library
    if not library:
        return f"ingest {attacker.name} (empty library)"
    card = library.pop(0)
    game.zones.player_zones[damaged_player_idx].exile.append(card)
    name = getattr(getattr(card, 'card_info', None), 'name', 'card')
    return f"ingest {attacker.name} exiled {name}"
