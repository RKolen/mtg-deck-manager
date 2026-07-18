"""Fetchland and similar sacrifice-to-search activated abilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.activated.core import ActivatedAbilitySpec
from engine.abilities.keywords.actions.library import shuffle_library
from engine.cards.land_mana import parse_produced_mana_from_oracle
from engine.abilities.keywords.other.shockland import apply_shockland_etb, has_shockland_etb
from engine.core.game_object import CardObject, Permanent
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_SEARCH_LAND_RE = re.compile(
    r'search your library for (?:a |an )?(.+?) card',
    re.IGNORECASE,
)
_LIFE_COST_RE = re.compile(r'pay (\d+) life', re.IGNORECASE)
_BASIC_LAND_NAMES = frozenset({'Plains', 'Island', 'Swamp', 'Mountain', 'Forest'})
_BASIC_TYPE_TO_COLOR = {
    'plains': 'W',
    'island': 'U',
    'swamp': 'B',
    'mountain': 'R',
    'forest': 'G',
}


@dataclass(frozen=True)
class PendingFetchland:
    """Paid fetchland activation waiting for a library choice."""

    source_uid: str
    effect_text: str
    life_paid: int
    did_tap: bool


@dataclass(frozen=True)
class FetchSearchOption:
    """One legal land choice during an interactive fetch."""

    library_idx: int
    name: str
    type_line: str


def is_fetchland_spec(spec: ActivatedAbilitySpec) -> bool:
    """Return True when the spec sacrifices and searches the library for a land."""
    cost = spec.cost_text.lower()
    effect = spec.effect_text.lower()
    return (
        'sacrifice' in cost
        and 'search your library' in effect
        and 'land' in effect
    )


def fetchland_life_cost(cost_text: str) -> int:
    """Parse life payment from an activation cost string."""
    match = _LIFE_COST_RE.search(cost_text)
    if match is None:
        return 0
    return int(match.group(1))


@dataclass(frozen=True)
class _LandSearchCriteria:
    """Parsed land search filter from oracle effect text."""

    type_names: tuple[str, ...]
    basic_only: bool
    enters_tapped: bool


def _parse_land_search(effect_text: str) -> _LandSearchCriteria | None:
    """Parse land type constraints from a search-library clause."""
    match = _SEARCH_LAND_RE.search(effect_text)
    if match is None:
        return None
    type_clause = match.group(1).strip()
    lowered = effect_text.lower()
    enters_tapped = (
        'onto the battlefield tapped' in lowered
        or 'put it onto the battlefield tapped' in lowered
    )
    if 'basic land' in type_clause.lower():
        return _LandSearchCriteria(
            type_names=(),
            basic_only=True,
            enters_tapped=enters_tapped,
        )
    parts = re.split(r', | or ', type_clause)
    names = tuple(part.strip() for part in parts if part.strip())
    if not names:
        return None
    return _LandSearchCriteria(
        type_names=names,
        basic_only=False,
        enters_tapped=enters_tapped,
    )


def _produced_colors(info: CardInfo) -> set[str]:
    """Return mana colors a land card can produce."""
    colors = set(info.produced_mana)
    if colors:
        return colors
    return set(parse_produced_mana_from_oracle(
        info.oracle_text,
        type_line=info.type_line,
    ))


def _land_type_matches(info: CardInfo, type_name: str) -> bool:
    """Return True when a card satisfies one named land type from the search."""
    type_line = info.type_line.lower()
    if 'land' not in type_line and not info.is_land:
        return False
    lowered_name = type_name.lower()
    if lowered_name in type_line:
        return True
    if info.name == type_name and info.is_land:
        return True
    color = _BASIC_TYPE_TO_COLOR.get(lowered_name)
    if color is not None and color in _produced_colors(info):
        return True
    return False


def _card_matches_search(info: CardInfo, criteria: _LandSearchCriteria) -> bool:
    """Return True when a library card satisfies the search filter."""
    if not info.is_land and 'land' not in info.type_line.lower():
        return False
    if criteria.basic_only:
        type_line = info.type_line.lower()
        if 'basic land' in type_line:
            return True
        return info.name in _BASIC_LAND_NAMES
    return any(
        _land_type_matches(info, type_name)
        for type_name in criteria.type_names
    )


def list_fetch_search_options(
    library: list,
    effect_text: str,
) -> list[FetchSearchOption]:
    """Return legal fetch choices aggregated by card name, sorted alphabetically."""
    criteria = _parse_land_search(effect_text)
    if criteria is None:
        return []
    by_name: dict[str, FetchSearchOption] = {}
    for idx, card in enumerate(library):
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        info = card.card_info
        if not _card_matches_search(info, criteria):
            continue
        if info.name not in by_name:
            by_name[info.name] = FetchSearchOption(
                library_idx=idx,
                name=info.name,
                type_line=info.type_line,
            )
    return sorted(by_name.values(), key=lambda option: option.name.lower())


def library_index_matches_fetch(
    library: list,
    effect_text: str,
    library_idx: int,
) -> bool:
    """Return True when the library card at library_idx can be fetched."""
    if library_idx < 0 or library_idx >= len(library):
        return False
    criteria = _parse_land_search(effect_text)
    if criteria is None:
        return False
    card = library[library_idx]
    if not isinstance(card, CardObject) or card.card_info is None:
        return False
    return _card_matches_search(card.card_info, criteria)


def complete_fetchland_at_index(
    game: GameState,
    perm: Permanent,
    effect_text: str,
    library_idx: int,
    *,
    pay_shockland_life: bool = False,
) -> str | None:
    """Sacrifice the fetchland and put the chosen library card onto the battlefield."""
    criteria = _parse_land_search(effect_text)
    if criteria is None:
        return None
    library = game.zones.player_zones[perm.controller_idx].library
    if not library_index_matches_fetch(library, effect_text, library_idx):
        return None
    card = library[library_idx]
    if not isinstance(card, CardObject) or card.card_info is None:
        return None
    fetch_name = card.card_info.name
    zones = game.zones
    controller_idx = perm.controller_idx
    zones.leave_battlefield(perm, Zone.GRAVEYARD, 'sacrifice', game)
    game.check_sbas()
    library.pop(library_idx)
    land_perm = zones.enter_battlefield(
        card,
        controller_idx,
        'fetchland',
        Zone.LIBRARY,
    )
    if criteria.enters_tapped:
        land_perm.tapped = True
    elif has_shockland_etb(card.card_info):
        player = game.players[controller_idx]
        etb_detail, player.life = apply_shockland_etb(
            land_perm,
            card.card_info,
            pay_life=pay_shockland_life,
            player_life=player.life,
        )
        if etb_detail:
            fetch_name = f"{fetch_name} — {etb_detail}"
    shuffle_library(zones, controller_idx)
    return f"{perm.name} fetched {fetch_name}"
