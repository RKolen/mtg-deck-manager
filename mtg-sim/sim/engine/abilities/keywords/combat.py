"""Combat keywords: evasion, damage, and blocking restrictions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword, is_artifact_creature, is_creature
from engine.abilities.keywords.registry import detect_keywords

if TYPE_CHECKING:
    from engine.core.game_object import Permanent
    from engine.core.game_state import GameState

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


def can_attack(perm: Permanent) -> bool:
    """Return whether a permanent can be declared as an attacker."""
    return (
        is_creature(perm)
        and not perm.tapped
        and not perm.sick
        and not has_keyword(perm, 'Defender')
    )


def can_block(perm: Permanent) -> bool:
    """Return whether a permanent can be declared as a blocker."""
    return is_creature(perm) and not perm.tapped


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
        return is_artifact_creature(blocker)
    if has_keyword(attacker, 'Intimidate'):
        return is_artifact_creature(blocker)
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


def lethal_damage_needed(source: Permanent, receiver: Permanent, receiver_toughness: int) -> int:
    """Return combat damage needed to destroy receiver from source."""
    if has_deathtouch(source):
        return 1
    return max(0, receiver_toughness - receiver.damage_marked)


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
