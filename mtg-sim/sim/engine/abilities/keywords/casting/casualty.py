"""Casualty: sacrifice a creature to copy an instant or sorcery spell."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent, effective_power
from engine.core.game_state import GameState
from engine.core.zones import Zone, ZoneManager

_CASUALTY_RE = re.compile(r'casualty\s+(\d+)', re.IGNORECASE)


def has_casualty(card: CardInfo) -> bool:
    """Return True when the spell has casualty."""
    if card.is_creature or card.is_land:
        return False
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Casualty') or bool(_CASUALTY_RE.search(text))


def has_casualty_card(card: CardInfo) -> bool:
    """Return True when the card has casualty."""
    return has_casualty(card)


def casualty_power_required(card: CardInfo) -> int:
    """Return the minimum power required for the casualty sacrifice."""
    match = _CASUALTY_RE.search(card.oracle_text or '')
    if match is None:
        return 0
    return int(match.group(1))


def normalize_paid_casualty(card: CardInfo, paid_casualty: bool) -> bool:
    """Return whether this cast pays casualty."""
    return paid_casualty and has_casualty(card)


def normalize_casualty_sacrifice_id(
    card: CardInfo,
    paid_casualty: bool,
    sacrifice_ids: list[int],
) -> int | None:
    """Return the permanent id to sacrifice for casualty, if any."""
    if not normalize_paid_casualty(card, paid_casualty):
        return None
    if not sacrifice_ids:
        return None
    return sacrifice_ids[0]


def _legal_casualty_sacrifice(perm: Permanent, card: CardInfo) -> bool:
    """Return True when a creature may be sacrificed for casualty."""
    if 'Creature' not in perm.type_line:
        return False
    required = casualty_power_required(card)
    return effective_power(perm) >= required


def casualty_sacrifice_error(
    zones: ZoneManager,
    player_idx: int,
    card: CardInfo,
    paid_casualty: bool,
    sacrifice_ids: list[int],
) -> str | None:
    """Return an error message when the casualty sacrifice is illegal."""
    message: str | None = None
    if not paid_casualty:
        if sacrifice_ids and has_casualty(card):
            message = f"{card.name} was not cast with casualty"
    elif not has_casualty(card):
        message = f"{card.name} does not have casualty"
    else:
        sacrifice_id = normalize_casualty_sacrifice_id(card, True, sacrifice_ids)
        if sacrifice_id is None:
            required = casualty_power_required(card)
            message = f"Casualty requires sacrificing a creature with power {required} or greater"
        else:
            perm = zones.find_permanent(sacrifice_id)
            if perm is None:
                message = f"Casualty sacrifice {sacrifice_id} not found"
            elif perm.controller_idx != player_idx:
                message = "Casualty may only sacrifice creatures you control"
            elif not _legal_casualty_sacrifice(perm, card):
                required = casualty_power_required(card)
                message = (
                    f"{perm.name} does not have power {required} or greater "
                    "for casualty"
                )
    return message


def sacrifice_for_casualty(
    zones: ZoneManager,
    game: GameState,
    sacrifice_id: int,
) -> Permanent:
    """Sacrifice a creature to pay casualty (call after casualty_sacrifice_error)."""
    perm = zones.find_permanent(sacrifice_id)
    assert perm is not None
    zones.leave_battlefield(perm, Zone.GRAVEYARD, 'casualty', game)
    return perm


def supports_casualty_copies(card: CardInfo) -> bool:
    """Return True when casualty copies are modeled for this spell type."""
    return has_casualty(card)
