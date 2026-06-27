"""Embalm: create an exiled token copy (simplified)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.casting.embalm import has_embalm as _has_embalm_on_card
from engine.abilities.keywords.other.embalm_token import create_embalm_token_in_exile
from engine.core.game_object import Permanent
from engine.core.zones import ZoneManager


def has_embalm(perm: Permanent) -> bool:
    """Return True when the permanent has embalm."""
    return has_keyword(perm, 'Embalm')


def has_embalm_card(card: CardInfo) -> bool:
    """Return True when the card has embalm."""
    return _has_embalm_on_card(card)


def apply_embalm_etb(zones: ZoneManager, permanent: Permanent) -> str | None:
    """Create a white Zombie token in exile (simplified embalm)."""
    if not has_embalm(permanent) or permanent.card_info is None:
        return None
    return create_embalm_token_in_exile(
        zones,
        permanent.controller_idx,
        permanent.card_info,
        source_obj_id=permanent.obj_id,
    )
