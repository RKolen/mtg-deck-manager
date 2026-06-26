"""Web-slinging: alternate cost by returning a tapped creature (CR 702.188)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.mana import ManaCost
from engine.core.zones import Zone, ZoneManager

_WEB_SLINGING_RE = re.compile(
    r'web[- ]slinging\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_web_slinging(card: CardInfo) -> bool:
    """Return True when the card has web-slinging."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Web-slinging') or bool(
        _WEB_SLINGING_RE.search(text)
    )


def web_slinging_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the web-slinging cost."""
    match = _WEB_SLINGING_RE.search(card.oracle_text or '')
    if match is None:
        return alt_cost_mana_needed(None, card)
    cost = ManaCost.parse(match.group(1))
    return alt_cost_mana_needed(cost, card)


def normalize_web_slinging_cast(card: CardInfo, cast_for_web_slinging: bool) -> bool:
    """Return whether this cast uses the web-slinging cost."""
    return cast_for_web_slinging and has_web_slinging(card)


def find_tapped_creature(
    zones: ZoneManager,
    controller_idx: int,
    uid: str | None,
) -> Permanent | None:
    """Return a tapped creature permanent owned by the controller."""
    if uid is None:
        return None
    try:
        found = zones.find_permanent(int(uid))
    except ValueError:
        return None
    if found is None:
        return None
    if (
        found.controller_idx == controller_idx
        and 'Creature' in found.type_line
        and found.tapped
    ):
        return found
    return None


def web_sling_creature_error(
    zones: ZoneManager,
    controller_idx: int,
    creature_uid: str | None,
    *,
    paid: bool,
) -> str | None:
    """Return an error when the web-slinging creature cost is illegal."""
    if not paid:
        return None
    if find_tapped_creature(zones, controller_idx, creature_uid) is None:
        return "Web-slinging requires returning a tapped creature you control"
    return None


def return_creature_for_web_sling(
    zones: ZoneManager,
    controller_idx: int,
    creature_uid: str | None,
) -> str | None:
    """Return a tapped creature to its owner's hand for web-slinging."""
    perm = find_tapped_creature(zones, controller_idx, creature_uid)
    if perm is None:
        return None
    zones.leave_battlefield(perm, Zone.HAND, 'web-slinging')
    return perm.name
