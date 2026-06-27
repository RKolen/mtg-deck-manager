"""Unit tests for batch 33 other keywords."""

from __future__ import annotations

from engine.abilities.keywords.other.commander_ninjutsu import (
    apply_commander_ninjutsu,
    assign_commander,
    commander_ninjutsu_mana_needed,
    has_commander_ninjutsu,
)
from engine.abilities.keywords.other.hidden_agenda import (
    apply_hidden_agenda_on_spell_cast,
    has_double_agenda,
    register_double_agenda,
    reveal_double_agenda,
)
from engine.abilities.keywords.other.hexproof_from import (
    has_hexproof_from,
    hexproof_from_qualities,
)
from engine.abilities.keywords.other.partner_with import (
    has_partner_with,
    validate_partner_with_deck,
)
from engine.abilities.keywords.other.toxic import (
    apply_toxic_on_player_damage,
    has_toxic,
)
from engine.abilities.keywords.targeting import can_target_permanent
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_card, make_creature, place_on_battlefield


def test_toxic_adds_poison_on_combat_damage():
    """Toxic gives poison counters when combat damage is dealt."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Toxic Frog', 1, 1, oracle='Toxic 2'),
        0,
        game.zones,
    )
    assert has_toxic(attacker)
    detail = apply_toxic_on_player_damage(game, attacker, 1, 1)
    assert detail is not None
    assert game.players[1].poison == 2


def test_hexproof_from_blocks_creature_targeting():
    """Hexproof from creatures blocks opposing creature spells."""
    game = fresh_game()
    target = place_on_battlefield(
        make_creature('Ward', 2, 2, oracle='Hexproof from creatures'),
        0,
        game.zones,
    )
    source_card = make_creature('Shooter', 1, 1)
    assert has_hexproof_from(target)
    assert 'creatures' in hexproof_from_qualities(target)
    assert not can_target_permanent(
        target,
        1,
        source_card=source_card,
    )
    assert can_target_permanent(
        target,
        0,
        source_card=source_card,
    )


def test_partner_with_requires_named_partner():
    """Partner with decks must include the named partner."""
    first = make_card(
        name='Thrasios',
        type_line='Legendary Creature — Merfolk Wizard',
        oracle='Partner with Tymna the Weaver',
    )
    second = make_card(
        name='Tymna the Weaver',
        type_line='Legendary Creature — Human Cleric',
        oracle='Partner with Thrasios, Triton Hero',
    )
    assert has_partner_with(first)
    assert validate_partner_with_deck([first]) is not None
    assert validate_partner_with_deck([first, second]) is None


def test_double_agenda_matches_after_reveal():
    """Double agenda logs when a revealed name matches a cast spell."""
    game = fresh_game()
    card = make_card(
        name='Conspiracy',
        type_line='Enchantment',
        oracle='Double agenda',
    )
    assert has_double_agenda(card)
    register_double_agenda(game, 0, 'Shock', 'Bolt')
    assert reveal_double_agenda(game, 0) is not None
    details = apply_hidden_agenda_on_spell_cast(game, 0, 'Shock')
    assert details
    assert 'double agenda matched' in details[0]


def test_commander_ninjutsu_puts_commander_on_battlefield():
    """Commander ninjutsu returns an attacker and deploys the commander."""
    game = fresh_game()
    attacker = place_on_battlefield(make_creature('Token', 1, 1), 0, game.zones)
    commander_info = make_creature(
        'Yuriko',
        2,
        2,
        oracle='Commander ninjutsu {1}{U}',
    )
    assert has_commander_ninjutsu(commander_info)
    assert commander_ninjutsu_mana_needed(commander_info) == 2
    commander = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=commander_info,
    )
    assign_commander(game, 0, commander)
    detail = apply_commander_ninjutsu(
        game,
        game.zones,
        0,
        str(attacker.obj_id),
    )
    assert detail is not None
    assert 'commander ninjutsu' in detail
    assert attacker in game.zones.player_zones[0].hand
    assert game.players[0].commander is None
    assert game.zones.battlefield[-1].name == 'Yuriko'
