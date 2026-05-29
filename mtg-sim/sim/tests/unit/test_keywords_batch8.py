"""Batch 8: encore ETB, ninjutsu, hand card client flags."""

from __future__ import annotations

from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.ninjutsu import apply_ninjutsu, has_ninjutsu
from engine.game.helpers import HandCastContext, card_to_client
from tests.conftest import add_to_hand, fresh_game, make_creature, place_on_battlefield


def test_encore_marks_on_etb():
    """Encore sets a counter when the creature enters."""
    game = fresh_game()
    creature = place_on_battlefield(
        make_creature('Siege', 3, 3, oracle='Encore {2}{B}'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, creature)
    assert any('encore' in detail for detail in details)
    assert creature.counters.get('encore') == 1


def test_card_to_client_exposes_evoke_and_bloodrush():
    """Hand serialisation includes evoke and bloodrush flags."""
    card = make_creature('Drifter', 2, 2, oracle='Flying\nEvoke {2}{U}')
    data = card_to_client(0, card, 10, HandCastContext())
    assert data['hasEvoke'] is True
    assert data['evokeAffordable'] is True

    rush = make_creature(
        'Ghor',
        4,
        4,
        oracle='Bloodrush — {R}, Discard Ghor: Target creature gets +4/+0.',
    )
    rush_data = card_to_client(0, rush, 5, HandCastContext())
    assert rush_data['canBloodrush'] is True


def test_ninjutsu_replaces_attacker():
    """Ninjutsu returns an attacker to hand and puts the ninja on the battlefield."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Elf', 1, 1),
        0,
        game.zones,
        sick=False,
    )
    ninja_card = make_creature(
        'Ninja',
        2,
        2,
        oracle='Ninjutsu {U}{B}',
    )
    assert has_ninjutsu(ninja_card)
    add_to_hand(ninja_card, 0, game.zones)
    detail = apply_ninjutsu(
        game,
        game.zones,
        0,
        0,
        str(attacker.obj_id),
    )
    assert detail is not None
    assert game.zones.find_permanent(attacker.obj_id) is None
    assert len(game.zones.player_zones[0].hand) == 1
