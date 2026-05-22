"""Unit tests for activated keyword modules (cycling, crew, unearth, channel)."""

from __future__ import annotations

from engine.abilities import activated
from engine.core.game_object import CardObject
from tests.conftest import (
    fresh_game,
    make_card,
    make_creature,
    make_instant,
    make_land,
    place_on_battlefield,
)


def test_cycling_discard_and_draw():
    """Cycling exiles the card from hand to graveyard after payment."""
    card = make_instant("Street Wraith", oracle="Cycling {2}\nDraw.")
    game = fresh_game()
    game.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=card),
        CardObject(controller_idx=0, owner_idx=0, card_info=make_land()),
    ]
    assert activated.has_cycling(card)
    assert activated.cycling_mana_needed(card) == 2
    assert activated.can_cycle(card, "main1", True)
    discarded = activated.cycle_from_hand(game.zones, 0, 0)
    assert discarded.card_info is not None
    assert discarded.card_info.name == "Street Wraith"
    assert len(game.zones.player_zones[0].hand) == 1


def test_unearth_returns_creature_with_counter():
    """Unearth puts a creature on the battlefield marked for exile."""
    creature = make_creature("Gravecrawler", oracle="Unearth {B}")
    game = fresh_game()
    game.zones.player_zones[0].graveyard = [
        CardObject(controller_idx=0, owner_idx=0, card_info=creature),
    ]
    perm = activated.unearth_from_graveyard(game.zones, 0, 0)
    assert activated.is_unearth_creature(perm)
    assert len(game.zones.battlefield) == 1


def test_crew_marks_vehicle_crewed():
    """Crew taps creatures and allows a vehicle to attack."""
    game = fresh_game()
    vehicle = place_on_battlefield(
        make_card(
            "Sky Skiff",
            type_line="Artifact — Vehicle",
            pt="3/3",
            oracle="Crew 1",
        ),
        0,
        game.zones,
    )
    crewer = place_on_battlefield(make_creature("Soldier", 1, 1), 0, game.zones)
    assert activated.has_crew(vehicle)
    assert activated.crew_cost(vehicle) == 1
    err = activated.crew_power_error(game, 0, [str(crewer.obj_id)], 1)
    assert err is None
    activated.apply_crew(game, vehicle, [str(crewer.obj_id)])
    assert activated.is_crewed_vehicle(vehicle)
    assert crewer.tapped


def test_channel_parses_cost_and_effect():
    """Channel parses mana cost and effect text."""
    card = make_instant(
        "Boseiju",
        oracle="Channel — {1}{G}, Discard Boseiju: Destroy target artifact or enchantment.",
    )
    assert activated.has_channel(card)
    assert activated.channel_mana_needed(card) == 2
    assert "destroy" in activated.channel_effect(card).lower()


def test_level_up_adds_counter():
    """Level up increases level and +1/+1 counters."""
    game = fresh_game()
    creature = place_on_battlefield(
        make_creature("Student", oracle="Level up {1}"),
        0,
        game.zones,
    )
    assert activated.has_level_up(creature)
    level = activated.apply_level_up(creature)
    assert level == 1
    assert creature.counters["+1/+1"] == 1
