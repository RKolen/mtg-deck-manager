"""Shared embalm token creation."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.core.game_object import TokenObject
from engine.core.zones import ZoneManager


def create_embalm_token_in_exile(
    zones: ZoneManager,
    player_idx: int,
    card: CardInfo,
    *,
    source_obj_id: int = 0,
) -> str:
    """Exile a white Zombie token copy (simplified embalm)."""
    power, toughness = '4', '4'
    if card.pt:
        parts = card.pt.split('/')
        if len(parts) == 2:
            power, toughness = parts[0], parts[1]
    name = f"{card.name} Token"
    token = TokenObject(
        controller_idx=player_idx,
        owner_idx=player_idx,
        name=name,
        type_line='Creature — Zombie',
        colors=['W'],
        power=power,
        toughness=toughness,
        oracle_text='',
        created_by_obj_id=source_obj_id,
    )
    zones.player_zones[player_idx].exile.append(token)
    return f"embalmed {name} (exile)"
