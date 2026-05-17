"""Integration tests for the Phase B interactive game loop."""

from engine.game import create_game, get_game, remove_game
from engine.core.game_object import CardObject
from engine.core.zones import Zone
from tests.conftest import make_card, make_deck, make_land


def test_create_game_returns_legacy_client_shape():
    """New engine exposes the same top-level fields consumed by play.tsx."""
    game = create_game(
        make_deck(lands=20),
        make_deck(lands=20),
        player_name="You",
        opponent_name="Opponent",
    )
    data = game.to_client()
    assert data["gameId"]
    assert data["phase"] == "mulligan"
    assert len(data["playerHand"]) == 7
    assert data["opponentHandCount"] == 7
    assert data["availableActions"] == ["keep", "mulligan"]


def test_keep_starts_first_main_phase_on_the_play():
    """Keeping on the play skips the first draw and enters main1."""
    game = create_game(make_deck(lands=20), make_deck(lands=20), on_the_play=True)
    data = game.action_keep()
    assert data["phase"] == "main1"
    assert len(data["playerHand"]) == 7
    assert "play_land" in data["availableActions"]


def test_mulligan_reduces_hand_size():
    """Mulligan shuffles back and draws one fewer card."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    data = game.action_mulligan()
    assert data["phase"] == "mulligan"
    assert len(data["playerHand"]) == 6


def test_play_land_moves_card_to_battlefield():
    """Playing a land uses ZoneManager and updates the client payload."""
    game = create_game([make_land() for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    data = game.action_play_land(0)
    assert data["playerLandPlayed"]
    assert len(data["playerBattlefield"]) == 1
    assert data["playerBattlefield"][0]["typeLine"].startswith("Basic Land")


def test_cast_zero_mana_creature_enters_battlefield():
    """A simple creature spell resolves onto the battlefield."""
    memnite = make_card(
        name="Memnite",
        type_line="Artifact Creature — Construct",
        cmc=0,
        pt="1/1",
        mana_cost="",
    )
    game = create_game([memnite for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    data = game.action_cast(0)
    assert len(data["playerBattlefield"]) == 1
    assert data["playerBattlefield"][0]["name"] == "Memnite"
    assert len(data["playerHand"]) == 6
    assert not data["stack"]


def test_cast_uses_stack_before_auto_resolution():
    """Casting a spell can expose the stack before priority passes resolve it."""
    memnite = make_card(
        name="Memnite",
        type_line="Artifact Creature — Construct",
        cmc=0,
        pt="1/1",
        mana_cost="",
    )
    game = create_game([memnite for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    data = game.action_cast_to_stack(0)
    assert data["stack"][0]["name"] == "Memnite"
    assert len(data["playerBattlefield"]) == 0
    game.action_pass_priority()
    resolved = game.action_pass_priority()
    assert not resolved["stack"]
    assert resolved["playerBattlefield"][0]["name"] == "Memnite"


def test_spell_with_illegal_target_fizzles_through_stack():
    """Target legality is checked when the stack object resolves."""
    shock = make_card(
        name="Shock",
        type_line="Instant",
        cmc=0,
        oracle="Shock deals 2 damage to any target.",
        mana_cost="",
    )
    bear = make_card(name="Bear", type_line="Creature — Bear", cmc=2, pt="2/2")
    game = create_game([shock for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    target_card = CardObject(controller_idx=1, owner_idx=1, card_info=bear)
    target = game.state.zones.enter_battlefield(target_card, 1, "test")
    game.action_cast_to_stack(0, target_uid=str(target.obj_id))
    game.state.zones.leave_battlefield(target, Zone.GRAVEYARD, "test")
    game.action_pass_priority()
    data = game.action_pass_priority()
    assert not data["stack"]
    assert data["opponentLife"] == 20
    assert "Shock" in data["playerGraveyard"]


def test_end_turn_returns_to_player_draw_when_opponent_has_no_attackers():
    """The simple opponent turn advances back to the player's draw phase."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    data = game.action_end_turn()
    assert data["phase"] == "draw"
    assert data["turn"] == 2


def test_game_session_store_round_trip_and_remove():
    """create_game registers sessions retrievable by FastAPI routes."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game_id = game.to_client()["gameId"]
    assert get_game(game_id) is game
    remove_game(game_id)
    assert get_game(game_id) is None
