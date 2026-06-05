"""Ability words: last unwired entries (Imprint, Repartee, council, Sweep)."""

from __future__ import annotations

from engine.abilities.activated.bloodrush import apply_bloodrush
from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.abilities.keywords.ability_words.spell_words import apply_spell_hosted_ability_words
from engine.core.game_object import (
    CardObject,
    effective_power,
    effective_toughness,
)
from engine.core.zones import Zone
from tests.ability_word_test_helpers import (
    assert_source_etb_trigger,
    fire_test_instant_cast,
    fresh_game_with_spell_cast_host,
    top_trigger,
)
from tests.conftest import (
    _CardStats,
    fresh_game,
    make_card,
    make_creature,
    make_instant,
    place_on_battlefield,
)


def test_imprint_triggers_on_etb():
    """Imprint registers an ETB trigger on the source permanent."""
    game = fresh_game()
    card = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_creature("Imprinter", 2, 2, oracle="Imprint — Draw a card."),
    )
    source = game.zones.enter_battlefield(card, 0, "test", Zone.HAND)
    register_permanent_ability_words(source, game.trigger_registry)
    assert_source_etb_trigger(game, source)


def test_repartee_triggers_when_opponent_attacks():
    """Repartee fires when an opponent declares an attacker."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Duelist", 2, 2, oracle="Repartee — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    attacker = place_on_battlefield(
        make_creature("Opp", 3, 3),
        1,
        game.zones,
        sick=False,
    )
    game.fire_attack_triggers(attacker)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_will_of_planeswalkers_requires_planeswalker():
    """Will of the Planeswalkers only fires while you control a planeswalker."""
    game, source = fresh_game_with_spell_cast_host(
        "Will of the Planeswalkers — Draw a card.",
        name="Vote Host",
    )
    spell = fire_test_instant_cast(game)
    assert game.stack.is_empty

    place_on_battlefield(
        make_card(name="Jace", type_line="Planeswalker", stats=_CardStats(cmc=4.0, pt="0/0")),
        0,
        game.zones,
    )
    game.fire_spell_cast_triggers(spell)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_spell_sweep_clause_on_cast():
    """Sweep on a spell applies its clause when the spell is cast."""
    game = fresh_game()
    card_info = make_instant("Sweeping Stroke", oracle="Sweep — Draw a card.")
    game.zones.player_zones[0].library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant("Top")),
    )
    details = apply_spell_hosted_ability_words(game, card_info, 0)
    assert any("Sweep" in detail and "drew" in detail for detail in details)
    assert len(game.zones.player_zones[0].hand) == 1


def test_bloodrush_grants_power_only():
    """Bloodrush grants +X/+0, not +1/+1 counters."""
    game = fresh_game()
    hand_card = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_card(
            name="Ghor-Clan Rampager",
            type_line="Creature — Beast",
            stats=_CardStats(cmc=4.0, pt="4/4"),
            oracle=(
                "Bloodrush — {R}, Discard this card: "
                "Target creature gets +4/+0 until end of turn."
            ),
            mana_cost="{2}{R}{G}",
        ),
    )
    game.zones.player_zones[0].hand.append(hand_card)
    target = place_on_battlefield(make_creature("Target", 2, 2), 0, game.zones)
    detail = apply_bloodrush(game.zones, 0, 0, str(target.obj_id))
    assert detail is not None
    assert target.counters.get('+power/+0') == 4
    assert target.counters.get('+1/+1', 0) == 0
    assert effective_power(target) == 6
    assert effective_toughness(target) == 2
