"""Unit tests for keyword action hooks (Mill, Scry, Fight, Surveil, Proliferate, ...)."""

from __future__ import annotations

from engine.abilities.keywords.actions import (
    ALL_KEYWORD_ACTIONS,
    ActionContext,
    amass_army,
    fight_creatures,
    has_fight,
    has_manifest,
    has_mill,
    has_scry,
    has_seek,
    has_surveil,
    manifest_top_of_library,
    mill_cards,
    proliferate,
    resolve_spell_keyword_actions,
    scry_cards,
    seek_card,
    surveil_cards,
)
from engine.abilities.keywords.actions.detect import keyword_actions_in_oracle
from engine.abilities.keywords.actions.resolve import _HANDLERS
from engine.core.game_object import CardObject, effective_power
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def test_all_seventy_two_keyword_actions_registered():
    """Scryfall keyword-action catalog has 72 entries."""
    assert len(ALL_KEYWORD_ACTIONS) == 72


def test_keyword_action_handler_coverage():
    """Most common keyword actions have resolution handlers (see plan.md)."""
    assert len(_HANDLERS) >= 71
    missing = [name for name in ALL_KEYWORD_ACTIONS if name not in _HANDLERS]
    assert 'Amass' not in missing
    assert 'Mill' not in missing
    assert 'Behold' not in missing
    assert 'Forage' not in missing


def test_amass_creates_army_with_counters():
    """Amass creates an Army token and adds +1/+1 counters."""
    game = fresh_game()
    detail = amass_army(game.zones, 0, 'Amass 2.')
    assert 'Army' in detail
    armies = [
        p for p in game.zones.battlefield
        if p.controller_idx == 0 and 'Army' in p.type_line
    ]
    assert len(armies) == 1
    assert armies[0].counters.get('+1/+1') == 2


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
    top = lib[0]
    second = lib[1]
    assert isinstance(top, CardObject)
    assert isinstance(second, CardObject)
    assert top.card_info is not None
    assert top.card_info.name == 'Second'
    assert second.card_info is not None
    assert second.card_info.name == 'Top'


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
    def draw_cards(player_idx: int, count: int) -> list[CardObject]:
        drawn: list[CardObject] = []
        for _ in range(count):
            card = game.zones.draw(player_idx)
            if card is None:
                break
            drawn.append(card)
        return drawn

    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Target player mills four cards.',
        draw_fn=draw_cards,
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
    assert has_seek('Seek a creature card.')
    assert has_manifest('Manifest the top card of your library.')


def test_seek_puts_matching_creature_in_hand():
    """Seek moves the first matching card from library to hand."""
    game = fresh_game()
    bear = CardObject(controller_idx=0, owner_idx=0, card_info=make_creature('Bear', 2, 2))
    bolt = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Bolt'))
    game.zones.player_zones[0].library.extend([bolt, bear])
    card = seek_card(game.zones, 0, 'Seek a creature card.')
    assert card is bear
    assert bear not in game.zones.player_zones[0].library


def test_manifest_puts_face_down_creature_on_battlefield():
    """Manifest puts the top library card face down as a 2/2."""
    game = fresh_game()
    hidden = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_creature('Hidden', 5, 5),
    )
    game.zones.player_zones[0].library.append(hidden)
    perm = manifest_top_of_library(game.zones, 0)
    assert perm is not None
    assert perm.face_down
    assert effective_power(perm) == 2


def test_forage_exiles_three_from_graveyard():
    """Forage exiles three cards from the controller's graveyard."""
    game = fresh_game()
    for idx in range(4):
        game.zones.player_zones[0].graveyard.append(
            CardObject(controller_idx=0, owner_idx=0, card_info=make_instant(f'G{idx}')),
        )
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Forage',
    ))
    assert 'foraged' in detail
    assert len(game.zones.player_zones[0].graveyard) == 1


def test_behold_reveals_top_card():
    """Behold logs the top card of the library."""
    game = fresh_game()
    game.zones.player_zones[0].library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Top Card')),
    )
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Behold',
    ))
    assert 'beheld Top Card' in detail


def test_resolve_seek_spell_action():
    """Seek on a spell resolves through ActionContext."""
    game = fresh_game()
    game.zones.player_zones[0].library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_creature('Bear', 2, 2)),
    )
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Seek a creature card.',
    ))
    assert 'sought Bear' in detail
    assert len(game.zones.player_zones[0].hand) == 1


def test_resolve_heist_exiles_opponent_top():
    """Heist exiles the top card of an opponent's library."""
    game = fresh_game()
    game.zones.player_zones[1].library.append(
        CardObject(controller_idx=1, owner_idx=1, card_info=make_instant('Stolen')),
    )
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Heist',
    ))
    assert 'heisted Stolen' in detail
    assert len(game.zones.player_zones[0].exile) == 1


def test_resolve_blight_puts_counter():
    """Blight puts a blight counter on a target creature."""
    game = fresh_game()
    target = place_on_battlefield(make_creature('Victim', 2, 2), 1, game.zones)
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Blight',
        target_creature_uid=str(target.obj_id),
    ))
    assert 'blighted' in detail
    assert target.counters.get('blight') == 1
