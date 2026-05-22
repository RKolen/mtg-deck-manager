"""Library-zone keyword actions: Mill, Scry, Surveil, Fateseal, Shuffle, Discover."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from engine.abilities.keywords.actions._parse import (
    parse_amount_after_keyword,
    parse_each_player_mill,
    parse_target_player_mill,
    word_to_int,
)
from engine.abilities.keywords.actions.detect import has_keyword_action
from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager

_MILLS_VERB_RE = re.compile(r'\bmills?\s+(\w+|\d+)', re.IGNORECASE)


def has_mill(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Mill action or 'mill(s) N'."""
    if not oracle_text:
        return False
    return has_keyword_action(oracle_text, 'Mill') or bool(_MILLS_VERB_RE.search(oracle_text))


def has_scry(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Scry action."""
    return has_keyword_action(oracle_text, 'Scry')


def has_surveil(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Surveil action."""
    return has_keyword_action(oracle_text, 'Surveil')


def has_fateseal(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Fateseal action."""
    return has_keyword_action(oracle_text, 'Fateseal')


def has_shuffle(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Shuffle action."""
    return has_keyword_action(oracle_text, 'Shuffle')


def has_discover(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Discover action."""
    return has_keyword_action(oracle_text, 'Discover')


def mill_count(oracle_text: str) -> int:
    """Parse how many cards to mill from oracle text."""
    each = parse_each_player_mill(oracle_text)
    if each:
        return each
    target = parse_target_player_mill(oracle_text)
    if target:
        return target
    mills_match = _MILLS_VERB_RE.search(oracle_text)
    if mills_match is not None:
        return word_to_int(mills_match.group(1))
    return parse_amount_after_keyword(oracle_text, 'mill')


def scry_count(oracle_text: str) -> int:
    """Parse how many cards to scry."""
    return parse_amount_after_keyword(oracle_text, 'scry')


def surveil_count(oracle_text: str) -> int:
    """Parse how many cards to surveil."""
    return parse_amount_after_keyword(oracle_text, 'surveil')


def mill_cards(zones: ZoneManager, player_idx: int, count: int) -> list[CardObject]:
    """Move the top count cards from library to graveyard."""
    lib = zones.player_zones[player_idx].library
    milled: list[CardObject] = []
    for _ in range(min(count, len(lib))):
        card = lib.pop(0)
        if isinstance(card, CardObject):
            zones.player_zones[player_idx].graveyard.append(card)
            milled.append(card)
    return milled


def scry_cards(
    zones: ZoneManager,
    player_idx: int,
    count: int,
    bottom_indices: tuple[int, ...] = (),
) -> int:
    """Reorder the top `count` cards; indices are 0-based from the top to put on bottom."""
    lib = zones.player_zones[player_idx].library
    if count <= 0 or not lib:
        return 0
    top = lib[:count]
    del lib[:count]
    bottom_set = set(bottom_indices)
    keep = [card for idx, card in enumerate(top) if idx not in bottom_set]
    bottom = [card for idx, card in enumerate(top) if idx in bottom_set]
    lib[:0] = keep
    lib.extend(bottom)
    return len(bottom)


def surveil_cards(zones: ZoneManager, player_idx: int, count: int) -> int:
    """Surveil N (MVP): put the top N cards into the graveyard."""
    milled = mill_cards(zones, player_idx, count)
    return len(milled)


def fateseal_cards(zones: ZoneManager, opponent_idx: int, count: int) -> int:
    """Fateseal N (MVP): put the top N cards of an opponent's library on the bottom."""
    lib = zones.player_zones[opponent_idx].library
    moved = min(count, len(lib))
    if moved <= 0:
        return 0
    top = lib[:moved]
    del lib[:moved]
    lib.extend(top)
    return moved


def shuffle_library(zones: ZoneManager, player_idx: int) -> None:
    """Randomize a player's library."""
    random.shuffle(zones.player_zones[player_idx].library)


@dataclass(frozen=True)
class DiscoverResult:
    """Card found by discover and cards put on the bottom."""

    hit: CardObject | None
    bottom_count: int


def discover_from_library(
    zones: ZoneManager,
    player_idx: int,
    max_mana_value: int,
) -> DiscoverResult:
    """Discover (MVP): exile from top until a nonland with MV <= max is found."""
    lib = zones.player_zones[player_idx].library
    bottom: list[CardObject] = []
    hit: CardObject | None = None
    while lib:
        card = lib.pop(0)
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        info = card.card_info
        if info.is_land:
            bottom.append(card)
            continue
        if int(info.cmc) <= max_mana_value:
            hit = card
            break
        bottom.append(card)
    lib.extend(bottom)
    return DiscoverResult(hit=hit, bottom_count=len(bottom))
