"""Unit tests for engine/rules/replacement.py (Phase E10)."""

from engine.abilities.keywords.handlers import grant_regeneration_shield
from engine.abilities.keywords.actions.library import mill_cards
from engine.abilities.keywords.casting._hand_discard import pop_hand_to_graveyard
from engine.core.game_object import CardObject
from engine.rules.replacement import (
    DamageEvent,
    ReplacementQueue,
    apply_damage_with_replacements,
)
from engine.rules.state_based import check_sbas
from tests.conftest import (
    fresh_game,
    make_card,
    make_creature,
    place_absorb_creature,
    place_on_battlefield,
)


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


def test_absorb_reduces_damage_in_replacement_queue():
    """Absorb is applied once via the damage replacement queue."""
    game = fresh_game()
    ward = place_absorb_creature(game)
    attacker = place_on_battlefield(make_creature('Raider', 3, 3), 1, game.zones)
    applied = apply_damage_with_replacements(game, ward, attacker, 3)
    assert applied == 1


def test_mill_with_leyline_sends_to_exile():
    """Leyline replaces graveyard destination when milling."""
    game = fresh_game()
    leyline = make_card(
        name='Leyline of the Void',
        type_line='Enchantment',
        oracle='If a card would be put into an opponent\'s graveyard, exile it instead.',
    )
    place_on_battlefield(leyline, 0, game.zones)
    for i in range(3):
        game.zones.player_zones[0].library.append(
            CardObject(
                controller_idx=0,
                owner_idx=0,
                card_info=make_card(name=f'Library Card {i}'),
            ),
        )
    mill_cards(game.zones, 0, 2, game)
    assert len(game.zones.player_zones[0].graveyard) == 0
    assert len(game.zones.player_zones[0].exile) == 2


def test_discard_with_leyline_sends_to_exile():
    """Leyline replaces graveyard destination when discarding from hand."""
    game = fresh_game()
    leyline = make_card(
        name='Leyline of the Void',
        type_line='Enchantment',
        oracle='If a card would be put into an opponent\'s graveyard, exile it instead.',
    )
    place_on_battlefield(leyline, 0, game.zones)
    game.zones.player_zones[0].hand.append(
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_card(name='Discard Me'),
        ),
    )
    pop_hand_to_graveyard(game.zones, 0, 0, game)
    assert len(game.zones.player_zones[0].graveyard) == 0
    assert len(game.zones.player_zones[0].exile) == 1


def test_replacement_chain_absorb_then_shield():
    """Self-replacements chain: Absorb reduces, then shield prevents the rest."""
    game = fresh_game()
    ward = place_absorb_creature(game)
    ward.counters['shield'] = 1
    attacker = place_on_battlefield(make_creature('Raider', 5, 5), 1, game.zones)
    applied = apply_damage_with_replacements(game, ward, attacker, 3)
    assert applied == 0
    assert ward.counters.get('shield', 0) == 0


def test_self_replacement_applies_before_other_effects():
    """CR 614.5: self-replacements apply before other replacement effects."""
    game = fresh_game()
    receiver = place_on_battlefield(make_creature('Target', 3, 3), 0, game.zones)
    order: list[str] = []

    def self_halve(_game, event: object) -> DamageEvent | None:
        if not isinstance(event, DamageEvent) or event.amount != 4:
            return None
        order.append('self')
        return DamageEvent(event.receiver_id, event.source_id, 2)

    def other_prevent(_game, event: object) -> DamageEvent | None:
        if not isinstance(event, DamageEvent) or event.amount != 2:
            return None
        order.append('other')
        return DamageEvent(event.receiver_id, event.source_id, 0)

    queue = ReplacementQueue()
    queue.register(other_prevent, self_replacement=False, source_obj_id=1)
    queue.register(self_halve, self_replacement=True, source_obj_id=receiver.obj_id)
    result = queue.apply(game, DamageEvent(receiver.obj_id, None, 4))
    assert isinstance(result, DamageEvent)
    assert result.amount == 0
    assert order == ['self', 'other']
