"""Unit tests for saddle, daybound, transfigure, training, and reconfigure (batch 28)."""

from __future__ import annotations

from engine.abilities.activated.mount import apply_mount, is_mounted
from engine.abilities.keywords.combat import can_attack
from engine.abilities.keywords.other.daybound import (
    apply_daybound_etb,
    has_daybound,
    is_daybound_front,
    resolve_daybound_upkeep,
)
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.reconfigure import (
    apply_reconfigure,
    can_reconfigure,
    has_reconfigure,
    is_reconfigure_creature,
)
from engine.abilities.keywords.other.saddle import has_saddle
from engine.abilities.keywords.other.training import apply_training_on_attack, has_training
from engine.abilities.keywords.other.transfigure import apply_transfigure, has_transfigure
from engine.core.game_object import CardObject
from tests.conftest import _CardStats, fresh_game, make_card, make_creature, place_on_battlefield


def test_saddle_creature_detected():
    """Creatures with saddle are recognized."""
    perm = place_on_battlefield(
        make_creature('Rider', 3, 3, oracle='Saddle 2'),
        0,
        fresh_game().zones,
    )
    assert has_saddle(perm)


def test_mounted_mount_can_attack():
    """A saddled mount can attack like a creature."""
    game = fresh_game()
    mount = place_on_battlefield(
        make_card(
            name='Steed',
            type_line='Creature — Mount',
            oracle='Mount 2',
            mana_cost='{2}',
            stats=_CardStats(cmc=2.0, pt='2/2'),
        ),
        0,
        game.zones,
    )
    rider = place_on_battlefield(make_creature('Rider', 3, 3), 0, game.zones)
    apply_mount(game, mount, [str(rider.obj_id)])
    mount.sick = False
    assert is_mounted(mount)
    assert can_attack(mount)


def test_daybound_toggles_on_upkeep():
    """Daybound permanents toggle faces at upkeep."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Wolf', 3, 3, oracle='Daybound'),
        0,
        game.zones,
    )
    assert has_daybound(perm)
    assert apply_daybound_etb(perm) is not None
    assert is_daybound_front(perm)
    details = resolve_daybound_upkeep(game, 0)
    assert details
    assert not is_daybound_front(perm)


def test_transfigure_sacrifices_and_tutors():
    """Transfigure sacrifices and finds a creature with the same CMC."""
    game = fresh_game()
    library = game.zones.player_zones[0].library
    library.append(
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_creature('Target', 2, 2, mana_cost='{1}{G}'),
        ),
    )
    perm = place_on_battlefield(
        make_creature('Shapeshifter', 2, 2, oracle='Transfigure {1}{G}', mana_cost='{1}{G}'),
        0,
        game.zones,
    )
    assert has_transfigure(perm)
    detail = apply_transfigure(game, perm)
    assert detail is not None
    assert 'Target' in detail
    assert len(game.zones.player_zones[0].hand) == 1


def test_training_puts_counter_when_stronger_ally_attacks():
    """Training grants +1/+1 when a stronger creature attacks with this."""
    game = fresh_game()
    trainee = place_on_battlefield(
        make_creature('Pupil', 1, 1, oracle='Training'),
        0,
        game.zones,
    )
    mentor = place_on_battlefield(make_creature('Veteran', 4, 4), 0, game.zones)
    assert has_training(trainee)
    detail = apply_training_on_attack(
        game,
        trainee,
        [str(trainee.obj_id), str(mentor.obj_id)],
    )
    assert detail is not None
    assert trainee.counters.get('+1/+1', 0) == 1


def test_reconfigure_toggles_creature_mode():
    """Reconfigure toggles between equipment and creature mode."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_card(
            name='Tool',
            type_line='Artifact — Equipment',
            oracle='Reconfigure',
            mana_cost='{2}',
            stats=_CardStats(cmc=2.0, pt='2/2'),
        ),
        0,
        game.zones,
    )
    assert has_reconfigure(perm)
    assert can_reconfigure(perm, game, 0, 'main1')
    detail = apply_reconfigure(perm)
    assert detail is not None
    assert is_reconfigure_creature(perm)
    perm.sick = False
    assert can_attack(perm)


def test_daybound_etb_hook_runs_from_registry():
    """Daybound is wired through apply_etb_other_abilities."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Dual', 2, 2, oracle='Daybound'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, perm)
    assert any('daybound' in line for line in details)
