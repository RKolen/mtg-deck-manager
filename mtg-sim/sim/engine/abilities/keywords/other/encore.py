"""Encore: exile from graveyard to create attacking token copies."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.activated._cost_keyword import (
    alt_cost_mana_value,
    has_cost_keyword,
    parse_alt_cost,
)
from engine.abilities.activated._cost_keyword import timing_allows_hand_activation
from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent, TokenObject
from engine.core.game_state import GameState
from engine.core.zones import Zone, ZoneManager
from engine.core.zone_card_lookup import graveyard_card_with_info

_ENCORE_RE = re.compile(
    r'encore\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_encore_card(card: CardInfo) -> bool:
    """Return True when the card has encore."""
    return card.is_creature and has_cost_keyword(card, 'Encore', _ENCORE_RE)


def has_encore(perm: Permanent) -> bool:
    """Return True when the permanent has encore."""
    return has_keyword(perm, 'Encore')


def encore_mana_needed(card: CardInfo) -> int:
    """Return generic mana to pay encore."""
    if parse_alt_cost(card, _ENCORE_RE) is None:
        return 0
    return alt_cost_mana_value(card, _ENCORE_RE)


def can_encore(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when encore may be activated from the graveyard."""
    if not has_encore_card(card):
        return False
    return timing_allows_hand_activation(phase, stack_is_empty)


def apply_encore_etb(permanent: Permanent) -> str | None:
    """Mark encore on ETB for client visibility."""
    if not has_encore(permanent):
        return None
    permanent.counters['encore'] = 1
    return f"{permanent.name} has encore"


def _token_copy_from_creature(
    card_info: CardInfo,
    controller_idx: int,
    *,
    source_obj_id: int = 0,
) -> TokenObject:
    """Build a token blueprint from a creature card."""
    return TokenObject(
        controller_idx=controller_idx,
        owner_idx=controller_idx,
        name=card_info.name,
        type_line=card_info.type_line,
        power=str(card_info.numeric_power),
        toughness=str(card_info.numeric_toughness),
        oracle_text=card_info.oracle_text or '',
        created_by_obj_id=source_obj_id,
    )


def _create_encore_tokens(
    game: GameState,
    card_info: CardInfo,
    player_idx: int,
    *,
    source_obj_id: int = 0,
) -> list[str]:
    """Create tapped attacking token copies for each opponent."""
    created: list[str] = []
    for opponent_idx in range(len(game.players)):
        if opponent_idx == player_idx:
            continue
        token = _token_copy_from_creature(
            card_info,
            player_idx,
            source_obj_id=source_obj_id,
        )
        perm = game.zones.enter_battlefield(token, player_idx, 'encore')
        perm.tapped = True
        perm.sick = False
        perm.counters['encore_attacking'] = opponent_idx + 1
        perm.counters['encore_sacrifice'] = 1
        created.append(card_info.name)
    return created


def apply_encore_from_graveyard(
    game: GameState,
    zones: ZoneManager,
    player_idx: int,
    graveyard_idx: int,
) -> str | None:
    """Exile a creature from graveyard and create encore token copies."""
    loaded = graveyard_card_with_info(zones, player_idx, graveyard_idx)
    if loaded is None:
        return None
    card, card_info = loaded
    if not has_encore_card(card_info):
        return None
    zones.exile_from_graveyard(card, player_idx)
    tokens = _create_encore_tokens(game, card_info, player_idx, source_obj_id=card.obj_id)
    if not tokens:
        return f"encore {card_info.name} (exiled, no opponents)"
    return f"encore {card_info.name} ({len(tokens)} token copy/copies)"


def sacrifice_encore_tokens(game: GameState, player_idx: int) -> list[str]:
    """Sacrifice encore tokens at the beginning of the next end step."""
    details: list[str] = []
    for perm in list(game.zones.battlefield):
        if perm.controller_idx != player_idx:
            continue
        if not perm.counters.pop('encore_sacrifice', 0):
            continue
        game.zones.leave_battlefield(perm, Zone.GRAVEYARD, 'encore', game)
        details.append(f"{perm.name} sacrificed (encore)")
    return details
