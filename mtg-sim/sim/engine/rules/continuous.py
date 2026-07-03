"""Continuous effects and the layer system (CR 613) — Phase E9."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords.registry import has_registered_keyword
from engine.rules.pt_base import raw_power_toughness

if TYPE_CHECKING:
    from engine.core.game_object import Modifier, Permanent
    from engine.core.game_state import GameState

_SUBLAYER_ORDER = {'a': 0, 'b': 1, 'c': 2, '': 3}


def effective_power(game: GameState, perm: Permanent) -> int:
    """Layered combat power for a permanent on the battlefield."""
    power, _ = _compute_layered_pt(game, perm)
    return power


def effective_toughness(game: GameState, perm: Permanent) -> int:
    """Layered toughness for SBAs and combat (may be 0)."""
    _, toughness = _compute_layered_pt(game, perm)
    return toughness


def abilities_suppressed(game: GameState, perm: Permanent) -> bool:
    """Return True when layer 6 removes all abilities from this permanent."""
    if 'Creature' not in perm.type_line:
        return False
    if _humility_active(game):
        return True
    return any(mod.remove_all_abilities for mod in perm.modifiers)


def has_creature_keyword(
    game: GameState | None,
    perm: Permanent,
    keyword: str,
) -> bool:
    """Keyword check respecting layer-6 ability removal."""
    if game is not None and abilities_suppressed(game, perm):
        return False
    return has_registered_keyword(perm.oracle_text, keyword)


def _compute_layered_pt(game: GameState, perm: Permanent) -> tuple[int, int]:
    base_power, base_toughness = _layer_7a_cda(game, perm)
    power, toughness = _layer_7b_set(game, perm, base_power, base_toughness)
    return _layer_7c_modify(perm, power, toughness)


def _layer_7a_cda(game: GameState, perm: Permanent) -> tuple[int, int]:
    power, toughness = raw_power_toughness(perm)
    if _is_tarmogoyf(perm):
        count = len(game.zones.player_zones[perm.controller_idx].graveyard)
        return count, count + 1
    for mod in _sorted_modifiers(perm):
        if mod.layer == 7 and mod.sublayer == 'a' and mod.cda_from_graveyard_count:
            count = len(game.zones.player_zones[perm.controller_idx].graveyard)
            power, toughness = count, count + 1
    return power, toughness


def _layer_7b_set(
    game: GameState,
    perm: Permanent,
    power: int,
    toughness: int,
) -> tuple[int, int]:
    if _humility_active(game) and 'Creature' in perm.type_line:
        power, toughness = 1, 1
    for mod in _sorted_modifiers(perm):
        if mod.layer != 7 or mod.sublayer != 'b':
            continue
        if mod.set_power is not None:
            power = mod.set_power
        if mod.set_toughness is not None:
            toughness = mod.set_toughness
    return power, toughness


def _layer_7c_modify(perm: Permanent, power: int, toughness: int) -> tuple[int, int]:
    power += perm.counters.get('+1/+1', 0)
    power += perm.counters.get('+power/+0', 0)
    power -= perm.counters.get('-1/-1', 0)
    toughness += perm.counters.get('+1/+1', 0)
    toughness -= perm.counters.get('-1/-1', 0)
    for mod in sorted(
        (m for m in perm.modifiers if m.layer == 7 and m.sublayer == 'c'),
        key=lambda m: (m.timestamp, m.source_obj_id),
    ):
        power += mod.power_delta
        toughness += mod.toughness_delta
    return power, toughness


def _sorted_modifiers(perm: Permanent) -> list[Modifier]:
    return sorted(
        perm.modifiers,
        key=lambda mod: (mod.layer, _SUBLAYER_ORDER.get(mod.sublayer, 9), mod.timestamp),
    )


def _humility_active(game: GameState) -> bool:
    return any(_is_humility(perm) for perm in game.zones.battlefield)


def _is_humility(perm: Permanent) -> bool:
    text = perm.oracle_text.lower()
    return (
        'Enchantment' in perm.type_line
        and 'all creatures lose all abilities' in text
        and '1/1' in text
    )


def _is_tarmogoyf(perm: Permanent) -> bool:
    return perm.name == 'Tarmogoyf' or '*+1' in perm.oracle_text
