"""Unit tests for engine/rules/continuous.py (layer system, Phase E9)."""

from engine.core.game_object import CardObject, Modifier, effective_power, effective_toughness
from engine.abilities.keywords.combat import has_deathtouch, lethal_damage_needed
from engine.abilities.keywords.targeting import can_target_permanent
from engine.rules.continuous import abilities_suppressed, has_creature_keyword
from tests.conftest import fresh_game, make_card, make_creature, place_on_battlefield


def _humility(game):
    oracle = (
        "All creatures lose all abilities and have base power and toughness 1/1."
    )
    info = make_card(
        name='Humility',
        type_line='Enchantment',
        oracle=oracle,
    )
    return place_on_battlefield(info, 0, game.zones)


def test_humility_makes_creatures_one_one_without_abilities():
    """Humility strips abilities and sets base P/T to 1/1 (layers 6 + 7b)."""
    game = fresh_game()
    _humility(game)
    dragon = place_on_battlefield(
        make_creature('Dragon', 5, 5, oracle='Flying. Indestructible.'),
        0,
        game.zones,
    )
    assert effective_power(dragon, game) == 1
    assert effective_toughness(dragon, game) == 1
    assert abilities_suppressed(game, dragon)
    assert not has_creature_keyword(game, dragon, 'Flying')
    assert not has_creature_keyword(game, dragon, 'Indestructible')


def test_tarmogoyf_pt_from_graveyard_count():
    """Tarmogoyf CDA sets P/T from its controller's graveyard size (layer 7a)."""
    game = fresh_game()
    for idx in range(10):
        game.zones.player_zones[0].graveyard.append(
            CardObject(
                controller_idx=0,
                owner_idx=0,
                card_info=make_creature(f'Card {idx}', 1, 1),
            )
        )
    goyf = place_on_battlefield(
        make_creature(
            name='Tarmogoyf',
            power=0,
            toughness=0,
            oracle='*+1',
        ),
        0,
        game.zones,
    )
    assert effective_power(goyf, game) == 10
    assert effective_toughness(goyf, game) == 11


def test_set_pt_overrides_earlier_set_then_counters_apply_in_7c():
    """Layer 7b sets use timestamp order; layer 7c counters modify afterward."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature('Bear', 2, 2), 0, game.zones)
    bear.modifiers.append(Modifier(layer=7, sublayer='b', set_power=3, set_toughness=3))
    bear.modifiers.append(Modifier(layer=7, sublayer='b', set_power=5, set_toughness=5))
    assert effective_power(bear, game) == 5
    assert effective_toughness(bear, game) == 5
    bear.counters['+1/+1'] = 2
    assert effective_power(bear, game) == 7
    assert effective_toughness(bear, game) == 7


def test_layer_7c_modifier_deltas_stack():
    """Multiple +X/+Y modifiers in sublayer 7c stack on the final P/T."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature('Bear', 2, 2), 0, game.zones)
    bear.modifiers.append(Modifier(layer=7, sublayer='c', power_delta=2, toughness_delta=1))
    bear.modifiers.append(Modifier(layer=7, sublayer='c', power_delta=1, toughness_delta=2))
    assert effective_power(bear, game) == 5
    assert effective_toughness(bear, game) == 5


def test_humility_strips_hexproof_for_targeting():
    """Layer 6 removes hexproof so opponents can target creatures under Humility."""
    game = fresh_game()
    oracle = (
        "All creatures lose all abilities and have base power and toughness 1/1."
    )
    place_on_battlefield(
        make_card(name='Humility', type_line='Enchantment', oracle=oracle),
        0,
        game.zones,
    )
    hexproof = place_on_battlefield(
        make_creature('Slippery', 2, 2, oracle='Hexproof.'),
        0,
        game.zones,
    )
    assert not can_target_permanent(hexproof, 1, game=game)


def test_humility_strips_deathtouch_in_combat():
    """Layer 6 removes deathtouch; lethal damage needs full toughness."""
    game = fresh_game()
    oracle = (
        "All creatures lose all abilities and have base power and toughness 1/1."
    )
    place_on_battlefield(
        make_card(name='Humility', type_line='Enchantment', oracle=oracle),
        0,
        game.zones,
    )
    snake = place_on_battlefield(
        make_creature('Snake', 1, 1, oracle='Deathtouch.'),
        0,
        game.zones,
    )
    bear = place_on_battlefield(make_creature('Bear', 2, 2), 1, game.zones)
    assert not has_deathtouch(snake, game)
    assert lethal_damage_needed(snake, bear, 2, game) == 2
