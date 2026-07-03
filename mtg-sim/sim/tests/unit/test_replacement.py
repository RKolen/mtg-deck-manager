"""Unit tests for engine/rules/replacement.py (Phase E10)."""

from engine.abilities.keywords.handlers import grant_regeneration_shield
from engine.rules.replacement import apply_damage_with_replacements
from engine.rules.state_based import check_sbas
from tests.conftest import fresh_game, make_card, make_creature, place_on_battlefield


def test_regeneration_shield_survives_lethal_damage():
    """Regeneration replaces destroy from lethal damage; creature stays on battlefield."""
    game = fresh_game()
    troll = place_on_battlefield(make_creature('Troll', 3, 3), 0, game.zones)
    grant_regeneration_shield(troll)
    troll.damage_marked = 3
    events = check_sbas(game)
    assert not any(e.rule == '704.5g' for e in events)
    assert troll in game.zones.battlefield
    assert troll.damage_marked == 0


def test_leyline_of_void_sends_destroyed_creature_to_exile():
    """Leyline replaces graveyard destination with exile."""
    game = fresh_game()
    leyline = make_card(
        name='Leyline of the Void',
        type_line='Enchantment',
        oracle='If a card would be put into an opponent\'s graveyard, exile it instead.',
    )
    place_on_battlefield(leyline, 0, game.zones)
    doomed = place_on_battlefield(make_creature('Doomed', 2, 2), 0, game.zones)
    doomed.damage_marked = 2
    check_sbas(game)
    assert doomed not in game.zones.battlefield
    assert len(game.zones.player_zones[0].graveyard) == 0
    assert len(game.zones.player_zones[0].exile) == 1


def test_shield_counter_prevents_combat_damage():
    """A shield counter is removed instead of marking damage."""
    game = fresh_game()
    defender = place_on_battlefield(make_creature('Defender', 2, 2), 0, game.zones)
    attacker = place_on_battlefield(make_creature('Attacker', 3, 3), 1, game.zones)
    defender.counters['shield'] = 1
    applied = apply_damage_with_replacements(game, defender, attacker, 2)
    assert applied == 0
    assert defender.damage_marked == 0
    assert defender.counters.get('shield', 0) == 0


def test_shield_counter_prevents_lethal_destroy():
    """A shield counter replaces destruction from lethal damage."""
    game = fresh_game()
    creature = place_on_battlefield(make_creature('Shielded', 2, 2), 0, game.zones)
    creature.counters['shield'] = 1
    creature.damage_marked = 2
    events = check_sbas(game)
    assert not any(e.rule == '704.5g' for e in events)
    assert creature in game.zones.battlefield
    assert creature.counters.get('shield', 0) == 0
