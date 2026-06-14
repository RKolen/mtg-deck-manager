"""Unit tests for horsemanship, epic, changeling, and fortify (batch 22)."""

from __future__ import annotations

from engine.abilities.keywords.combat import legal_blocker
from engine.abilities.keywords.other.changeling import (
    CreatureTypeRef,
    has_changeling,
    shares_creature_type,
)
from engine.abilities.keywords.other.epic import has_epic, resolve_epic_upkeep
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.fortify import apply_fortify_etb
from engine.abilities.keywords.other.horsemanship import horsemanship_allows_block
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_card, make_creature, place_on_battlefield


def test_horsemanship_blocks_non_horsemanship_blockers():
    """Only horsemanship creatures can block horsemanship attackers."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Knight', 2, 2, oracle='Horsemanship'),
        0,
        game.zones,
    )
    blocker = place_on_battlefield(make_creature('Soldier', 2, 2), 1, game.zones)
    assert not horsemanship_allows_block(blocker, attacker)
    assert not legal_blocker(blocker, attacker, game)


def test_epic_casts_creature_from_graveyard():
    """Epic returns a creature from the graveyard to the battlefield at upkeep."""
    game = fresh_game()
    epic_card = make_creature('Dragon', 5, 5, oracle='Epic')
    assert has_epic(epic_card)
    game.zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=epic_card),
    )
    details = resolve_epic_upkeep(game, 0)
    assert details
    assert any('epic cast' in line for line in details)
    assert len(game.zones.battlefield) == 1


def test_changeling_matches_any_creature_type():
    """Changeling shares a creature type with every creature."""
    changeling = make_creature('Shapeshifter', 1, 1, oracle='Changeling')
    perm = place_on_battlefield(changeling, 0, fresh_game().zones)
    assert has_changeling(perm)
    assert shares_creature_type(
        CreatureTypeRef(perm.type_line, perm=perm),
        CreatureTypeRef('Creature — Elf Warrior'),
    )


def test_changeling_helps_amplify_via_type_match():
    """Changeling in hand counts toward amplify via shared type matching."""
    game = fresh_game()
    changeling_card = make_creature('Shapeshifter', 1, 1, oracle='Changeling')
    game.zones.player_zones[0].hand.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=changeling_card),
    )
    amplified = place_on_battlefield(
        make_card('Sliver', type_line='Creature — Sliver', oracle='Amplify 2'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, amplified)
    assert any('amplify' in line for line in details)
    assert amplified.counters.get('+1/+1', 0) == 2


def test_fortify_attaches_to_land():
    """Fortify equipment attaches to a land on ETB."""
    game = fresh_game()
    place_on_battlefield(make_card('Plains', type_line='Land'), 0, game.zones)
    equipment = place_on_battlefield(
        make_card('Hammer', type_line='Artifact — Equipment', oracle='Fortify 3'),
        0,
        game.zones,
    )
    detail = apply_fortify_etb(game, equipment)
    assert detail is not None
    assert equipment.attached_to is not None


def test_fortify_etb_hook_runs_from_registry():
    """Fortify is wired through apply_etb_other_abilities."""
    game = fresh_game()
    place_on_battlefield(make_card('Island', type_line='Land'), 0, game.zones)
    equipment = place_on_battlefield(
        make_card('Lens', type_line='Artifact — Equipment', oracle='Fortify 2'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, equipment)
    assert any('fortify' in line for line in details)
