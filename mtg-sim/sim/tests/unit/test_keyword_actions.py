"""Unit tests for keyword action hooks (Mill, Scry, Fight, Surveil, Proliferate, ...)."""

from __future__ import annotations

from engine.abilities.keywords.actions import (
    ALL_KEYWORD_ACTIONS,
    ActionContext,
    fight_creatures,
    has_fight,
    has_mill,
    has_scry,
    has_surveil,
    mill_cards,
    proliferate,
    resolve_spell_keyword_actions,
    scry_cards,
    surveil_cards,
)
from engine.abilities.keywords.actions.detect import keyword_actions_in_oracle
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def test_all_seventy_two_keyword_actions_registered():
    """Scryfall keyword-action catalog has 72 entries."""
    assert len(ALL_KEYWORD_ACTIONS) == 72


def test_mill_moves_library_to_graveyard():
    """Mill puts the top cards of a library into the graveyard."""
    game = fresh_game()
    for idx in range(5):
        game.zones.player_zones[0].library.append(
            CardObject(
                controller_idx=0,
                owner_idx=0,
                card_info=make_instant(f'Card{idx}'),
            ),
        )
    milled = mill_cards(game.zones, 0, 3)
    assert len(milled) == 3
    assert len(game.zones.player_zones[0].library) == 2
    assert len(game.zones.player_zones[0].graveyard) == 3


def test_scry_puts_selected_cards_on_bottom():
    """Scry reorders the top of the library."""
    game = fresh_game()
    cards = [
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Top')),
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Second')),
    ]
    game.zones.player_zones[0].library.extend(cards)
    scry_cards(game.zones, 0, 2, bottom_indices=(0,))
    lib = game.zones.player_zones[0].library
    assert lib[0].card_info is not None
    assert lib[0].card_info.name == 'Second'
    assert lib[1].card_info is not None
    assert lib[1].card_info.name == 'Top'


def test_surveil_mills_to_graveyard():
    """Surveil (MVP) moves the top cards into the graveyard."""
    game = fresh_game()
    game.zones.player_zones[0].library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('A')),
    )
    count = surveil_cards(game.zones, 0, 1)
    assert count == 1
    assert len(game.zones.player_zones[0].graveyard) == 1


def test_fight_deals_mutual_power_damage():
    """Fight makes each creature deal damage equal to its power to the other."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature('Bear', 2, 3), 0, game.zones)
    wolf = place_on_battlefield(make_creature('Wolf', 4, 2), 1, game.zones)
    fight_creatures(bear, wolf)
    assert bear.damage_marked == 4
    assert wolf.damage_marked == 2


def test_proliferate_increments_poison_and_counters():
    """Proliferate adds one to each counter type present."""
    game = fresh_game()
    game.players[0].poison = 2
    creature = place_on_battlefield(make_creature('Grim', 1, 1), 0, game.zones)
    creature.counters['+1/+1'] = 1
    details = proliferate(game)
    assert game.players[0].poison == 3
    assert creature.counters['+1/+1'] == 2
    assert details


def test_resolve_mill_spell_on_stack():
    """A spell whose only effect is mill resolves via keyword actions."""
    game = fresh_game()
    for idx in range(4):
        game.zones.player_zones[1].library.append(
            CardObject(
                controller_idx=1,
                owner_idx=1,
                card_info=make_instant(f'G{idx}'),
            ),
        )
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Target player mills four cards.',
        draw_fn=game.zones.draw,
    ))
    assert 'milled 4' in detail
    assert len(game.zones.player_zones[1].graveyard) == 4


def test_keyword_actions_detect_in_order():
    """Multiple keyword actions appear in left-to-right oracle order."""
    oracle = 'Surveil 2, then draw a card. Mill one.'
    assert keyword_actions_in_oracle(oracle)[0] == 'Surveil'
    assert 'Mill' in keyword_actions_in_oracle(oracle)


def test_has_mill_scry_fight_detect_oracle():
    """Common action detectors match oracle reminders."""
    assert has_mill('Target player mills ten cards.')
    assert has_scry('Scry 2.')
    assert has_fight('Fight target creature.')
    assert has_surveil('Surveil 1.')
