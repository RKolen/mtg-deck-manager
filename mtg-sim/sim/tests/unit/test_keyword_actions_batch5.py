"""Unit tests for keyword actions batch 5.

Discover, Fateseal, Shuffle, Collect evidence, Discard, and Venture.
"""

from __future__ import annotations

from engine.abilities.keywords.actions.library import (
    discover_from_library,
    fateseal_cards,
    has_discover,
    has_fateseal,
    has_shuffle,
    shuffle_library,
)
from engine.abilities.keywords.actions.specialty import (
    collect_evidence,
    discard_from_hand,
    has_collect_evidence,
    has_discard_action,
    has_venture,
    venture_into_dungeon,
)
from engine.core.game_object import CardObject
from tests.conftest import add_to_hand, fresh_game, make_instant, make_land


def test_discover_finds_first_matching_nonland():
    """Discover exiles until it finds a spell within the mana value."""
    game = fresh_game()
    library = game.zones.player_zones[0].library
    library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_land('Forest', 'G')),
    )
    library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Bolt', cmc=1.0)),
    )
    assert has_discover('Discover 3.')
    result = discover_from_library(game.zones, 0, 3)
    assert result.hit is not None
    assert result.hit.card_info is not None
    assert result.hit.card_info.name == 'Bolt'
    assert result.bottom_count == 1


def test_fateseal_puts_opponent_cards_on_library_bottom():
    """Fateseal moves the top cards of an opponent's library to the bottom."""
    game = fresh_game()
    opponent_lib = game.zones.player_zones[1].library
    for label in ('First', 'Second', 'Third'):
        opponent_lib.append(
            CardObject(
                controller_idx=1,
                owner_idx=1,
                card_info=make_instant(label, cmc=1.0),
            ),
        )
    assert has_fateseal('Fateseal 2.')
    moved = fateseal_cards(game.zones, 1, 2)
    assert moved == 2
    top = opponent_lib[0]
    assert isinstance(top, CardObject)
    assert top.card_info is not None
    assert top.card_info.name == 'Third'


def test_shuffle_randomizes_library_order():
    """Shuffle keeps the library size while reordering cards."""
    game = fresh_game()
    library = game.zones.player_zones[0].library
    for idx in range(6):
        library.append(
            CardObject(
                controller_idx=0,
                owner_idx=0,
                card_info=make_instant(f'Card {idx}'),
            ),
        )
    before = [
        card.card_info.name
        for card in library
        if isinstance(card, CardObject) and card.card_info is not None
    ]
    assert has_shuffle('Shuffle your library.')
    shuffle_library(game.zones, 0)
    after = [
        card.card_info.name
        for card in library
        if isinstance(card, CardObject) and card.card_info is not None
    ]
    assert len(after) == len(before)
    assert set(after) == set(before)


def test_collect_evidence_requires_six_graveyard_cards():
    """Collect evidence succeeds with six or more cards in the graveyard."""
    game = fresh_game()
    graveyard = game.zones.player_zones[0].graveyard
    for idx in range(6):
        graveyard.append(
            CardObject(
                controller_idx=0,
                owner_idx=0,
                card_info=make_instant(f'Clue {idx}'),
            ),
        )
    assert has_collect_evidence('Collect evidence.')
    detail = collect_evidence(game.zones, 0)
    assert detail is not None
    assert 'collected evidence' in detail


def test_discard_action_moves_hand_card_to_graveyard():
    """Discard keyword action moves a card from hand to graveyard."""
    game = fresh_game()
    card = make_instant('Junk')
    add_to_hand(card, 0, game.zones)
    assert has_discard_action('Discard.')
    detail = discard_from_hand(game.zones, 0)
    assert 'discarded' in detail
    assert len(game.zones.player_zones[0].hand) == 0
    assert len(game.zones.player_zones[0].graveyard) == 1


def test_venture_advances_dungeon_room_counter():
    """Venture into the dungeon advances the player's dungeon room."""
    game = fresh_game()
    assert has_venture('Venture into the dungeon.')
    assert game.players[0].dungeon_room == 0
    detail = venture_into_dungeon(game, 0)
    assert 'dungeon room 1' in detail
    assert game.players[0].dungeon_room == 1
