"""Champion: ETB exile another creature until this leaves the battlefield."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import CardObject, Permanent
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_CHAMPION_EXILE_COUNTER = 'champion_exile_obj'


def has_champion(perm: Permanent) -> bool:
    """Return True when the permanent has champion."""
    return has_keyword(perm, 'Champion')


def _pick_champion_host(
    battlefield: list[Permanent],
    champion: Permanent,
) -> Permanent | None:
    others = [
        perm for perm in battlefield
        if perm.obj_id != champion.obj_id
        and perm.controller_idx == champion.controller_idx
        and 'Creature' in perm.type_line
    ]
    if not others:
        return None
    return min(others, key=lambda perm: perm.obj_id)


def apply_champion_etb(game: GameState, champion: Permanent) -> str | None:
    """Exile another creature you control under champion."""
    if not has_champion(champion):
        return None
    host = _pick_champion_host(game.zones.battlefield, champion)
    if host is None:
        return f"champion {champion.name} (no host)"
    game.zones.leave_battlefield(host, Zone.EXILE, 'champion', game)
    card = host.source
    if isinstance(card, CardObject):
        champion.counters[_CHAMPION_EXILE_COUNTER] = card.obj_id
    return f"champion {champion.name} exiled {host.name}"


def release_championed_creature(game: GameState, champion: Permanent) -> str | None:
    """Return the championed creature to the battlefield when champion leaves."""
    exile_id = champion.counters.pop(_CHAMPION_EXILE_COUNTER, None)
    if exile_id is None:
        return None
    player_idx = champion.controller_idx
    exile = game.zones.player_zones[player_idx].exile
    for idx, card in enumerate(exile):
        if not isinstance(card, CardObject):
            continue
        if card.obj_id != exile_id:
            continue
        exile.pop(idx)
        game.zones.enter_battlefield(card, player_idx, 'champion_return', Zone.EXILE)
        name = card.card_info.name if card.card_info else 'creature'
        return f"champion released {name}"
    return None
