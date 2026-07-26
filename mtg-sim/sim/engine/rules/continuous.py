"""Continuous effects and the layer system (CR 613) — Phase E9."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords.registry import has_registered_keyword
from engine.rules.pt_base import raw_power_toughness

if TYPE_CHECKING:
    from engine.core.game_object import Permanent
    from engine.core.game_state import GameState
    from engine.core.modifier import Modifier

_SUBLAYER_ORDER = {'a': 0, 'b': 1, 'c': 2, 'd': 3, 'e': 4, '': 5}


def effective_power(game: GameState, perm: Permanent) -> int:
    """Layered combat power for a permanent on the battlefield."""
    power, _ = _compute_layered_pt(game, perm)
    return power


def effective_toughness(game: GameState, perm: Permanent) -> int:
    """Layered toughness for SBAs and combat (may be 0)."""
    _, toughness = _compute_layered_pt(game, perm)
    return toughness


def effective_controller(perm: Permanent) -> int:
    """Controller after layer-2 control-changing effects."""
    override: int | None = None
    for mod in _sorted_modifiers(perm):
        if mod.layer == 2 and mod.controller_override is not None:
            override = mod.controller_override
    if override is not None:
        return override
    return perm.controller_idx


def effective_type_line(perm: Permanent) -> str:
    """Type line after layer-4 type-changing effects."""
    types = _base_type_words(perm.type_line)
    for mod in _sorted_modifiers(perm):
        if mod.layer != 4:
            continue
        for removed in mod.removed_types:
            types.discard(removed)
        for added in mod.added_types:
            types.add(added)
    return ' '.join(sorted(types, key=_type_sort_key))


def effective_colors(perm: Permanent) -> tuple[str, ...]:
    """Colors after layer-5 color-changing effects.

    Base colors come from the mana cost pips when no layer-5 set is present.
    """
    colors: tuple[str, ...] | None = None
    for mod in _sorted_modifiers(perm):
        if mod.layer == 5 and mod.set_colors is not None:
            colors = mod.set_colors
    if colors is not None:
        return colors
    return _colors_from_mana_cost(perm)


def _colors_from_mana_cost(perm: Permanent) -> tuple[str, ...]:
    cost = perm.card_info.mana_cost if perm.card_info is not None else ''
    found = [pip for pip in ('W', 'U', 'B', 'R', 'G') if pip in cost.upper()]
    return tuple(found)


def abilities_suppressed(game: GameState, perm: Permanent) -> bool:
    """Return True when layer 6 removes all abilities from this permanent."""
    if 'Creature' not in effective_type_line(perm):
        return False
    if _humility_active(game):
        return True
    return any(mod.remove_all_abilities for mod in perm.modifiers)


def has_creature_keyword(
    game: GameState | None,
    perm: Permanent,
    keyword: str,
) -> bool:
    """Keyword check respecting layer-6 ability removal and grants."""
    if game is not None and abilities_suppressed(game, perm):
        return False
    needle = keyword.casefold()
    for mod in _sorted_modifiers(perm):
        if mod.layer != 6:
            continue
        if any(granted.casefold() == needle for granted in mod.granted_keywords):
            return True
    return has_registered_keyword(perm.oracle_text, keyword)


def _compute_layered_pt(game: GameState, perm: Permanent) -> tuple[int, int]:
    base_power, base_toughness = _layer_7a_cda(game, perm)
    power, toughness = _layer_7b_set(game, perm, base_power, base_toughness)
    power, toughness = _layer_7c_modify(perm, power, toughness)
    power, toughness = _layer_7d_counters(perm, power, toughness)
    return _layer_7e_switch(perm, power, toughness)


def _layer_7a_cda(game: GameState, perm: Permanent) -> tuple[int, int]:
    """Characteristic-defining abilities (layer 7a).

    CDAs are abilities: when layer 6 removes all abilities (Humility), they do
    not apply — the classic dependency between Humility and Tarmogoyf.
    """
    power, toughness = raw_power_toughness(perm)
    if abilities_suppressed(game, perm):
        return power, toughness
    if _is_tarmogoyf(perm):
        count = len(game.zones.player_zones[effective_controller(perm)].graveyard)
        return count, count + 1
    for mod in _sorted_modifiers(perm):
        if mod.layer == 7 and mod.sublayer == 'a' and mod.cda_from_graveyard_count:
            count = len(game.zones.player_zones[effective_controller(perm)].graveyard)
            power, toughness = count, count + 1
    return power, toughness


def _layer_7b_set(
    game: GameState,
    perm: Permanent,
    power: int,
    toughness: int,
) -> tuple[int, int]:
    if _humility_active(game) and _is_creatureish(perm):
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
    for mod in sorted(
        (m for m in perm.modifiers if m.layer == 7 and m.sublayer == 'c'),
        key=lambda m: (m.timestamp, m.source_obj_id),
    ):
        power += mod.power_delta
        toughness += mod.toughness_delta
    return power, toughness


def _layer_7d_counters(perm: Permanent, power: int, toughness: int) -> tuple[int, int]:
    power += perm.counters.get('+1/+1', 0)
    power += perm.counters.get('+power/+0', 0)
    power -= perm.counters.get('-1/-1', 0)
    toughness += perm.counters.get('+1/+1', 0)
    toughness -= perm.counters.get('-1/-1', 0)
    return power, toughness


def _layer_7e_switch(perm: Permanent, power: int, toughness: int) -> tuple[int, int]:
    for mod in sorted(
        (m for m in perm.modifiers if m.layer == 7 and (m.sublayer == 'e' or m.switch_pt)),
        key=lambda m: (m.timestamp, m.source_obj_id),
    ):
        if mod.switch_pt:
            power, toughness = toughness, power
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


def _is_creatureish(perm: Permanent) -> bool:
    return 'Creature' in perm.type_line or 'Creature' in effective_type_line(perm)


def _base_type_words(type_line: str) -> set[str]:
    cleaned = type_line.replace('—', ' ').replace('-', ' ')
    return {part for part in cleaned.split() if part}


def _type_sort_key(word: str) -> tuple[int, str]:
    order = {
        'Legendary': 0,
        'Basic': 1,
        'Snow': 2,
        'World': 3,
        'Artifact': 4,
        'Enchantment': 5,
        'Creature': 6,
        'Land': 7,
        'Planeswalker': 8,
        'Instant': 9,
        'Sorcery': 10,
        'Tribal': 11,
        'Kindred': 11,
    }
    return (order.get(word, 50), word)
