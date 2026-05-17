"""Unit tests for engine/core/game_state.py."""

from tests.conftest import (
    add_to_hand,
    fresh_game,
    fresh_zones,
    make_card,
    make_deck,
    place_on_battlefield,
)


def test_game_state_check_sbas_delegates_to_state_based_actions():
    """GameState.check_sbas applies SBAs and updates winner."""
    game = fresh_game(player_life=0)
    events = game.check_sbas()
    assert any(event.rule == "704.5a" for event in events)
    assert game.winner == 1


def test_to_client_hides_opponent_hand_contents():
    """Opponent hand count is public, but card identities are hidden."""
    game = fresh_game()
    add_to_hand(make_card("Player Card"), 0, game.zones)
    add_to_hand(make_card("Secret Opponent Card"), 1, game.zones)
    data = game.to_client()
    assert data["player"]["hand"] == ["Player Card"]
    assert data["opponent"]["handCount"] == 1
    assert "hand" not in data["opponent"]


def test_to_client_serialises_battlefield_permanents():
    """Battlefield permanents use Permanent.to_dict for public board state."""
    game = fresh_game()
    perm = place_on_battlefield(make_card("Elite Vanguard", pt="2/1"), 0, game.zones)
    data = game.to_client()
    assert data["battlefield"]["player"][0]["objId"] == perm.obj_id
    assert data["battlefield"]["player"][0]["name"] == "Elite Vanguard"
    assert data["battlefield"]["player"][0]["power"] == 2


def test_make_deck_adds_requested_lands():
    """make_deck returns explicit cards followed by deterministic basic lands."""
    deck = make_deck(make_card("Spell"), lands=2)
    assert [card.name for card in deck] == ["Spell", "Plains", "Plains"]


def test_fresh_zones_loads_libraries():
    """fresh_zones loads test cards into player and opponent libraries."""
    zones = fresh_zones(
        player_cards=[make_card("Player Library Card")],
        opponent_cards=[make_card("Opponent Library Card")],
    )
    player_card = zones.player_zones[0].library[0].card_info
    opponent_card = zones.player_zones[1].library[0].card_info
    assert player_card is not None
    assert opponent_card is not None
    assert player_card.name == "Player Library Card"
    assert opponent_card.name == "Opponent Library Card"
