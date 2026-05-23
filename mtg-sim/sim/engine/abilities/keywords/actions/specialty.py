"""Keyword actions: Behold, Exert, Forage, Detain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords.actions.detect import has_keyword_action
from engine.abilities.keywords.actions.targets import find_creature_by_uid
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState
    from engine.core.zones import ZoneManager


def has_behold(oracle_text: str | None) -> bool:
    """Return True when oracle text includes Behold."""
    return has_registered_keyword(oracle_text, 'Behold')


def has_exert(oracle_text: str | None) -> bool:
    """Return True when oracle uses Exert as a keyword action."""
    return has_keyword_action(oracle_text, 'Exert')


def has_forage(oracle_text: str | None) -> bool:
    """Return True when oracle uses Forage as a keyword action."""
    return has_keyword_action(oracle_text, 'Forage')


def has_detain(oracle_text: str | None) -> bool:
    """Return True when oracle uses Detain as a keyword action."""
    return has_keyword_action(oracle_text, 'Detain')


def behold_top_card(zones: ZoneManager, controller_idx: int) -> str:
    """Reveal the top card of the library (simplified Behold)."""
    library = zones.player_zones[controller_idx].library
    if not library:
        return 'beheld (empty library)'
    top = library[-1]
    if isinstance(top, CardObject) and top.card_info is not None:
        name = top.card_info.name
        is_land = top.card_info.is_land
    else:
        name = 'unknown'
        is_land = False
    return f"beheld {name}" + (' (land)' if is_land else '')


def behold_draw_if_clause(oracle_text: str, zones: ZoneManager, controller_idx: int) -> str | None:
    """Draw a card when Behold is followed by a draw clause."""
    lowered = oracle_text.lower()
    if 'behold' not in lowered or 'draw' not in lowered:
        return None
    drawn = zones.draw(controller_idx)
    if drawn is None:
        return 'drew 0 (empty library)'
    name = drawn.card_info.name if isinstance(drawn, CardObject) and drawn.card_info else 'card'
    return f"drew {name}"


def exert_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Exert a target creature: tap it and skip its next untap step."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['exerted'] = 1
    target.tapped = True
    return f"exerted {target.name}"


def forage_cost(zones: ZoneManager, controller_idx: int, game: GameState | None) -> str | None:
    """Forage: exile three cards from your graveyard or sacrifice a Food."""
    graveyard = zones.player_zones[controller_idx].graveyard
    if len(graveyard) >= 3:
        for _ in range(3):
            graveyard.pop()
        return 'foraged (exiled 3 from graveyard)'
    for perm in list(zones.battlefield):
        if perm.controller_idx != controller_idx:
            continue
        if 'Food' not in perm.type_line:
            continue
        if game is None:
            return None
        zones.leave_battlefield(perm, Zone.GRAVEYARD, 'sacrifice', game)
        return f"foraged (sacrificed {perm.name})"
    return None


def detain_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Detain a creature: tap it and it won't untap during its controller's next untap."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['detained'] = 1
    target.tapped = True
    return f"detained {target.name}"
