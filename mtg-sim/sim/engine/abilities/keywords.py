"""
Keyword ability hooks for combat, targeting, and timing (Phase E11).

All 359 Scryfall keywords (abilities, actions, ability words) are registered in
keyword_registry_data.py and detected via keyword_registry.detect_keywords().
Category hooks implement rules where the simplified engine supports them.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keyword_registry import detect_keywords, has_registered_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from deck_registry import CardInfo
    from engine.core.game_state import GameState

_PROTECTION_RE = re.compile(r"protection from ([a-z]+)", re.IGNORECASE)
_COLOR_ALIASES = {
    "w": "white",
    "u": "blue",
    "b": "black",
    "r": "red",
    "g": "green",
}
_LANDWALK_SUFFIXES = (
    ('islandwalk', 'island'),
    ('swampwalk', 'swamp'),
    ('mountainwalk', 'mountain'),
    ('forestwalk', 'forest'),
    ('plainswalk', 'plains'),
    ('legendary landwalk', 'legendary'),
    ('nonbasic landwalk', 'nonbasic'),
    ('landwalk', 'land'),
)


def has_keyword(perm: Permanent, keyword: str) -> bool:
    """Return True when the permanent's oracle text contains keyword."""
    return has_registered_keyword(perm.oracle_text, keyword)


def list_keywords(perm: Permanent) -> frozenset[str]:
    """Return every Scryfall keyword detected on this permanent."""
    return detect_keywords(perm.oracle_text)


def has_flash(card: CardInfo) -> bool:
    """Return True when a spell may be cast at instant speed via Flash."""
    return (
        has_registered_keyword(card.oracle_text or '', 'Flash')
        or 'Instant' in card.type_line
    )


def enters_ready(perm: Permanent) -> bool:
    """Return True when a creature should not have summoning sickness on ETB."""
    return has_keyword(perm, 'Haste')


def can_attack(perm: Permanent) -> bool:
    """Return whether a permanent can be declared as an attacker."""
    return (
        _is_creature(perm)
        and not perm.tapped
        and not perm.sick
        and not has_keyword(perm, 'Defender')
    )


def can_block(perm: Permanent) -> bool:
    """Return whether a permanent can be declared as a blocker."""
    return _is_creature(perm) and not perm.tapped


def legal_blocker(blocker: Permanent, attacker: Permanent, game: GameState) -> bool:
    """Return whether blocker may block attacker (evasion keywords)."""
    del game
    if not can_block(blocker):
        return False
    if has_keyword(attacker, 'Flying'):
        return has_keyword(blocker, 'Flying') or has_keyword(blocker, 'Reach')
    if has_keyword(attacker, 'Shadow'):
        return has_keyword(blocker, 'Shadow')
    if has_keyword(attacker, 'Fear'):
        return _is_artifact_creature(blocker)
    if has_keyword(attacker, 'Intimidate'):
        return _is_artifact_creature(blocker)
    return True


def menace_requires_two_blockers(attacker: Permanent) -> bool:
    """Return True when menace requires at least two blockers."""
    return has_keyword(attacker, 'Menace')


def has_enough_blockers(attacker: Permanent, blockers: list[Permanent]) -> bool:
    """Return True when declared blockers satisfy menace."""
    if menace_requires_two_blockers(attacker):
        return len(blockers) >= 2
    return bool(blockers)


def should_tap_attacker(attacker: Permanent) -> bool:
    """Return True when declaring an attack should tap the attacker."""
    return not has_keyword(attacker, 'Vigilance')


def deals_in_first_strike_step(perm: Permanent) -> bool:
    """Return True when the permanent assigns damage in the first-strike step."""
    return has_keyword(perm, 'First strike') or has_keyword(perm, 'Double strike')


def deals_in_regular_step(perm: Permanent) -> bool:
    """Return True when the permanent assigns damage in the regular damage step."""
    return has_keyword(perm, 'Double strike') or not deals_in_first_strike_step(perm)


def has_lifelink(perm: Permanent) -> bool:
    """Return True when combat damage from this permanent gains life."""
    return has_keyword(perm, 'Lifelink')


def has_trample(perm: Permanent) -> bool:
    """Return True when excess combat damage may trample to the player."""
    return has_keyword(perm, 'Trample')


def has_deathtouch(perm: Permanent) -> bool:
    """Return True when any combat damage from this permanent is lethal."""
    return has_keyword(perm, 'Deathtouch')


def has_infect(perm: Permanent) -> bool:
    """Return True when combat damage gives poison or -1/-1 counters."""
    return has_keyword(perm, 'Infect')


def has_wither(perm: Permanent) -> bool:
    """Return True when damage to creatures gives -1/-1 counters."""
    return has_keyword(perm, 'Wither')


def has_persist(perm: Permanent) -> bool:
    """Return True when the creature returns with -1/-1 if it had none."""
    return has_keyword(perm, 'Persist')


def has_undying(perm: Permanent) -> bool:
    """Return True when the creature returns with +1/+1 if it had none."""
    return has_keyword(perm, 'Undying')


def has_modular(perm: Permanent) -> bool:
    """Return True when the creature has modular."""
    return has_keyword(perm, 'Modular')


def lethal_damage_needed(source: Permanent, receiver: Permanent, receiver_toughness: int) -> int:
    """Return combat damage needed to destroy receiver from source."""
    if has_deathtouch(source):
        return 1
    return max(0, receiver_toughness - receiver.damage_marked)


def is_indestructible(perm: Permanent) -> bool:
    """Return True when lethal damage and destroy effects do not destroy this permanent."""
    return has_keyword(perm, 'Indestructible')


def has_hexproof(perm: Permanent) -> bool:
    """Return True when opponents cannot target this permanent."""
    return has_keyword(perm, 'Hexproof')


def has_shroud(perm: Permanent) -> bool:
    """Return True when no player can target this permanent."""
    return has_keyword(perm, 'Shroud')


def has_ward(perm: Permanent) -> bool:
    """Return True when the permanent has ward."""
    return has_keyword(perm, 'Ward')


def protection_qualities(perm: Permanent) -> frozenset[str]:
    """Return protection qualities parsed from oracle text (e.g. 'red', 'creatures')."""
    return frozenset(match.group(1).lower() for match in _PROTECTION_RE.finditer(perm.oracle_text))


def has_protection_from(
    perm: Permanent,
    *,
    source_is_creature: bool = False,
    source_colors: frozenset[str] | None = None,
) -> bool:
    """Return True when protection prevents interaction from the described source."""
    qualities = protection_qualities(perm)
    if not qualities and has_keyword(perm, 'Protection'):
        qualities = frozenset({'all'})
    if not qualities:
        return False
    if 'all' in qualities:
        return True
    if source_is_creature and 'creatures' in qualities:
        return True
    if source_colors:
        normalized = {_normalize_protection_color(color) for color in source_colors}
        if qualities.intersection(normalized):
            return True
    return False


def can_target_permanent(
    target: Permanent,
    controller_idx: int,
    *,
    source_is_creature: bool = False,
    source_colors: frozenset[str] | None = None,
) -> bool:
    """Return True when controller_idx may target target with a spell or ability."""
    if has_shroud(target):
        return False
    if has_hexproof(target) and controller_idx != target.controller_idx:
        return False
    if has_ward(target) and controller_idx != target.controller_idx:
        return False
    if has_protection_from(
        target,
        source_is_creature=source_is_creature,
        source_colors=source_colors,
    ):
        return False
    return True


def landwalk_unblockable(attacker: Permanent, defending_player_idx: int, game: GameState) -> bool:
    """Return True when a landwalk ability makes the attacker unblockable."""
    present = {name.lower() for name in detect_keywords(attacker.oracle_text)}
    for walk_key, land_needle in _LANDWALK_SUFFIXES:
        if walk_key not in present:
            continue
        if _defender_controls_land_type(game, defending_player_idx, land_needle):
            return True
    return False


def _defender_controls_land_type(game: GameState, player_idx: int, land_type: str) -> bool:
    needle = land_type.lower()
    for perm in game.zones.permanents_of(player_idx):
        if 'Land' not in perm.type_line:
            continue
        if needle == 'land':
            return True
        if needle == 'legendary' and 'Legendary' in perm.type_line:
            return True
        if needle == 'nonbasic' and 'Basic' not in perm.type_line:
            return True
        if needle in perm.name.lower() or needle in perm.type_line.lower():
            return True
    return False


def _is_creature(perm: Permanent) -> bool:
    return 'Creature' in perm.type_line


def _is_artifact_creature(perm: Permanent) -> bool:
    return 'Artifact' in perm.type_line and 'Creature' in perm.type_line


def _normalize_protection_color(color: str) -> str:
    """Map mana letters and color names to protection quality strings."""
    lowered = color.lower()
    if len(lowered) == 1 and lowered in _COLOR_ALIASES:
        return _COLOR_ALIASES[lowered]
    return lowered
