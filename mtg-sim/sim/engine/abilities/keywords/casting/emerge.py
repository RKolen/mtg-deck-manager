"""Emerge: cast a creature for its emerge cost by sacrificing a permanent (CR 702.118)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.game_state import GameState
from engine.core.mana import ManaCost
from engine.core.zones import Zone, ZoneManager

_EMERGE_COST_RE = re.compile(
    r'emerge\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_emerge(card: CardInfo) -> bool:
    """Return True when the creature may be cast for its emerge cost."""
    if not card.is_creature:
        return False
    return has_registered_keyword(card.oracle_text, 'Emerge') or bool(
        _EMERGE_COST_RE.search(card.oracle_text or '')
    )


def has_emerge_card(card: CardInfo) -> bool:
    """Return True when the card has emerge."""
    return has_emerge(card)


def emerge_cost(card: CardInfo) -> ManaCost | None:
    """Parse the emerge alternate cost from oracle text."""
    match = _EMERGE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def emerge_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the emerge cost instead of the mana cost."""
    return alt_cost_mana_needed(emerge_cost(card), card)


def emerge_allows_artifact_sacrifice(card: CardInfo) -> bool:
    """Return True when an artifact may be sacrificed for emerge."""
    return 'sacrifice an artifact or creature' in (card.oracle_text or '').lower()


def normalize_emerge_cast(card: CardInfo, cast_for_emerge: bool) -> bool:
    """Return whether this cast uses emerge."""
    return cast_for_emerge and has_emerge(card)


def normalize_emerge_sacrifice_id(
    card: CardInfo,
    cast_for_emerge: bool,
    sacrifice_ids: list[int],
) -> int | None:
    """Return the permanent id to sacrifice for emerge, if any."""
    if not normalize_emerge_cast(card, cast_for_emerge):
        return None
    if not sacrifice_ids:
        return None
    return sacrifice_ids[0]


def _legal_emerge_sacrifice(perm: Permanent, card: CardInfo) -> bool:
    """Return True when a permanent may be sacrificed for emerge."""
    if 'Creature' in perm.type_line:
        return True
    return 'Artifact' in perm.type_line and emerge_allows_artifact_sacrifice(card)


def emerge_sacrifice_error(
    zones: ZoneManager,
    player_idx: int,
    card: CardInfo,
    cast_for_emerge: bool,
    sacrifice_ids: list[int],
) -> str | None:
    """Return an error message when the emerge sacrifice is illegal."""
    message: str | None = None
    if not cast_for_emerge:
        if sacrifice_ids and has_emerge(card):
            message = f"{card.name} was not cast for emerge"
    elif not has_emerge(card):
        message = f"{card.name} does not have emerge"
    else:
        sacrifice_id = normalize_emerge_sacrifice_id(card, True, sacrifice_ids)
        if sacrifice_id is None:
            message = "Emerge requires sacrificing a creature or artifact"
        else:
            perm = zones.find_permanent(sacrifice_id)
            if perm is None:
                message = f"Emerge sacrifice {sacrifice_id} not found"
            elif perm.controller_idx != player_idx:
                message = "Emerge may only sacrifice permanents you control"
            elif not _legal_emerge_sacrifice(perm, card):
                if 'Artifact' in perm.type_line:
                    message = f"{perm.name} is not a legal emerge sacrifice"
                else:
                    message = f"{perm.name} is not a creature or artifact"
    return message


def sacrifice_for_emerge(
    zones: ZoneManager,
    game: GameState,
    sacrifice_id: int,
) -> Permanent:
    """Sacrifice a permanent to pay emerge (call after emerge_sacrifice_error)."""
    perm = zones.find_permanent(sacrifice_id)
    assert perm is not None
    zones.leave_battlefield(perm, Zone.GRAVEYARD, 'emerge', game)
    return perm
