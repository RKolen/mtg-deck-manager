"""Integration tests for the Phase B interactive game loop."""

from deck_registry import CardInfo
from engine.game import _GameConfig, create_game, get_game, remove_game
from engine.core.game_object import CardObject, Effect, GameObject
from engine.core.game_state import GameState
from engine.core.zones import Zone
from engine.rules.triggers import TriggerKey, TriggerSpec, is_attacks, is_beginning_of_combat
from engine.rules.triggers import is_beginning_of_upkeep, is_blocks, is_dies
from engine.rules.triggers import is_draws_card, is_end_step, is_enters_battlefield
from engine.rules.triggers import is_spell_cast
from tests.conftest import _CardStats, make_card, make_creature, make_deck, make_land
from tests.conftest import place_on_battlefield


def test_create_game_returns_legacy_client_shape():
    """New engine exposes the same top-level fields consumed by play.tsx."""
    game = create_game(
        make_deck(lands=20),
        make_deck(lands=20),
        _GameConfig(player_name="You", opponent_name="Opponent"),
    )
    data = game.to_client()
    assert data["gameId"]
    assert data["phase"] == "mulligan"
    assert len(data["playerHand"]) == 7
    assert data["opponentHandCount"] == 7
    assert data["availableActions"] == ["keep", "mulligan"]


def test_keep_starts_first_main_phase_on_the_play():
    """Keeping on the play skips the first draw and enters main1."""
    game = create_game(make_deck(lands=20), make_deck(lands=20), _GameConfig(on_the_play=True))
    data = game.action_keep()
    assert data["phase"] == "main1"
    assert len(data["playerHand"]) == 7
    assert "play_land" in data["availableActions"]


def test_draw_card_trigger_resolves_from_turn_draw():
    """Draw-card triggers emitted by the turn draw resolve before main phase."""
    game = create_game(make_deck(lands=20), make_deck(lands=20), _GameConfig(on_the_play=True))
    game.action_keep()
    observer = place_on_battlefield(make_creature("Draw Observer", 1, 1), 0, game.state.zones)
    game.action_end_turn()
    game.state.trigger_registry.register(
        observer,
        TriggerKey.DRAWS_CARD,
        TriggerSpec(condition=is_draws_card, effect=_GainLifeEffect(player_idx=0, amount=1)),
    )

    data = game.action_draw()

    assert data["playerLife"] == 21
    assert data["phase"] == "main1"
    assert not data["stack"]


def test_london_mulligan_draws_seven_then_bottoms_on_keep():
    """Each mulligan redraws 7, then keep bottoms one card per mulligan."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    data = game.action_mulligan()
    assert data["phase"] == "mulligan"
    assert len(data["playerHand"]) == 7
    data = game.action_mulligan()
    assert len(data["playerHand"]) == 7
    data = game.action_keep()
    assert data["phase"] == "main1"
    assert len(data["playerHand"]) == 5
    assert any(entry["action"] == "mulligan_bottom" for entry in data["log"])


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
        stats=_CardStats(cmc=0.0, pt="1/1"),
        mana_cost="",
    )
    game = create_game([memnite for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    data = game.action_cast(0)
    assert len(data["playerBattlefield"]) == 1
    assert data["playerBattlefield"][0]["name"] == "Memnite"
    assert len(data["playerHand"]) == 6
    assert not data["stack"]


def test_etb_trigger_resolves_from_creature_spell_resolution():
    """ETB triggers emitted by resolving creature spells resolve through the stack."""
    memnite = make_card(
        name="Memnite",
        type_line="Artifact Creature — Construct",
        stats=_CardStats(cmc=0.0, pt="1/1"),
        mana_cost="",
    )
    game = create_game([memnite for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    observer = place_on_battlefield(
        make_creature("Soul Warden", 1, 1),
        0,
        game.state.zones,
    )
    game.state.trigger_registry.register(
        observer,
        TriggerKey.ENTERS_BATTLEFIELD,
        TriggerSpec(
            condition=is_enters_battlefield,
            effect=_GainLifeEffect(player_idx=0, amount=1),
        ),
    )

    data = game.action_cast(0)

    assert data["playerLife"] == 21
    assert not data["stack"]


def test_cast_uses_stack_before_auto_resolution():
    """Casting a spell can expose the stack before priority passes resolve it."""
    memnite = make_card(
        name="Memnite",
        type_line="Artifact Creature — Construct",
        stats=_CardStats(cmc=0.0, pt="1/1"),
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


def test_cast_spell_trigger_goes_above_cast_spell_on_stack():
    """Spell-cast triggers emitted by the game loop sit above the cast spell."""
    memnite = make_card(
        name="Memnite",
        type_line="Artifact Creature — Construct",
        stats=_CardStats(cmc=0.0, pt="1/1"),
        mana_cost="",
    )
    game = create_game([memnite for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    observer = place_on_battlefield(
        make_creature("Cast Observer", 1, 1),
        0,
        game.state.zones,
    )
    game.state.trigger_registry.register(
        observer,
        TriggerKey.SPELL_CAST,
        TriggerSpec(condition=is_spell_cast),
    )

    data = game.action_cast_to_stack(0)

    assert data["stack"][0]["type"] == "TriggeredAbilityOnStack"
    assert data["stack"][1]["name"] == "Memnite"


def test_triggered_ability_effect_resolves_before_spell_below_it():
    """Triggered ability effects resolve from the stack before the spell underneath."""
    memnite = make_card(
        name="Memnite",
        type_line="Artifact Creature — Construct",
        stats=_CardStats(cmc=0.0, pt="1/1"),
        mana_cost="",
    )
    game = create_game([memnite for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    observer = place_on_battlefield(
        make_creature("Cast Observer", 1, 1),
        0,
        game.state.zones,
    )
    game.state.trigger_registry.register(
        observer,
        TriggerKey.SPELL_CAST,
        TriggerSpec(condition=is_spell_cast, effect=_GainLifeEffect(player_idx=0, amount=1)),
    )

    data = game.action_cast_to_stack(0)
    assert data["stack"][0]["type"] == "TriggeredAbilityOnStack"

    game.action_pass_priority()
    data = game.action_pass_priority()

    assert data["playerLife"] == 21
    assert data["stack"][0]["name"] == "Memnite"
    assert len(data["playerBattlefield"]) == 1


def test_instant_can_be_cast_while_spell_is_on_stack():
    """Instants can be cast at priority while another spell is pending."""
    memnite = make_card(
        name="Memnite",
        type_line="Artifact Creature — Construct",
        stats=_CardStats(cmc=0.0, pt="1/1"),
        mana_cost="",
    )
    shock = make_card(
        name="Shock",
        type_line="Instant",
        stats=_CardStats(cmc=0.0, pt="0/0"),
        oracle="Shock deals 2 damage to any target.",
        mana_cost="",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=memnite),
    ]
    data = game.action_cast_to_stack(0)
    assert data["availableActions"] == ["pass_priority"]

    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=shock),
    ]
    data = game.to_client()
    assert "cast_spell" in data["availableActions"]
    data = game.action_cast(0, target_player=1)
    assert not data["stack"]
    assert data["opponentLife"] == 18
    assert data["playerBattlefield"][0]["name"] == "Memnite"
    assert "Shock" in data["playerGraveyard"]


def test_sorcery_speed_spell_unavailable_while_stack_is_not_empty():
    """Non-instant spells cannot be cast in response windows."""
    memnite = make_card(
        name="Memnite",
        type_line="Artifact Creature — Construct",
        stats=_CardStats(cmc=0.0, pt="1/1"),
        mana_cost="",
    )
    divination = make_card(
        name="Divination",
        type_line="Sorcery",
        stats=_CardStats(cmc=0.0, pt="0/0"),
        oracle="Draw two cards.",
        mana_cost="",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=memnite),
    ]
    game.action_cast_to_stack(0)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=divination),
    ]
    assert game.to_client()["availableActions"] == ["pass_priority"]


def test_spell_with_illegal_target_fizzles_through_stack():
    """Target legality is checked when the stack object resolves."""
    shock = make_card(
        name="Shock",
        type_line="Instant",
        stats=_CardStats(cmc=0.0, pt="0/0"),
        oracle="Shock deals 2 damage to any target.",
        mana_cost="",
    )
    bear = make_card(name="Bear", type_line="Creature — Bear", stats=_CardStats(cmc=2.0, pt="2/2"))
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


def test_dies_trigger_resolves_from_removal_spell_resolution():
    """Dies triggers emitted by removal spells resolve through the stack."""
    doom_blade = make_card(
        name="Doom Blade",
        type_line="Instant",
        stats=_CardStats(cmc=0.0, pt="0/0"),
        oracle="Destroy target creature.",
        mana_cost="",
    )
    game = create_game([doom_blade for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    observer = place_on_battlefield(
        make_creature("Blood Artist", 0, 1),
        0,
        game.state.zones,
    )
    target = place_on_battlefield(make_creature("Bear", 2, 2), 1, game.state.zones)
    game.state.trigger_registry.register(
        observer,
        TriggerKey.DIES,
        TriggerSpec(condition=is_dies, effect=_GainLifeEffect(player_idx=0, amount=1)),
    )

    data = game.action_cast(0, target_uid=str(target.obj_id))

    assert data["playerLife"] == 21
    assert not data["stack"]
    assert "Doom Blade" in data["playerGraveyard"]


def test_phyrexian_life_payment_casts_with_no_mana():
    """Phyrexian mana can be paid with life when no mana is available."""
    growth = make_card(
        name="Mutagenic Growth",
        type_line="Instant",
        stats=_CardStats(cmc=1.0, pt="0/0"),
        oracle="Target creature gets +2/+2 until end of turn.",
        mana_cost="{G/P}",
    )
    creature = make_card(
        name="Hero",
        type_line="Creature — Human",
        stats=_CardStats(cmc=0.0, pt="1/1"),
        mana_cost="",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=creature),
        CardObject(controller_idx=0, owner_idx=0, card_info=growth),
    ]
    game.action_cast(0)
    target = game.state.zones.creatures_of(0)[0]
    data = game.action_cast(0, target_uid=str(target.obj_id))
    assert data["playerLife"] == 18
    assert "Mutagenic Growth" in data["playerGraveyard"]


def test_heroic_token_created_when_targeted_by_spell():
    """The Phase B loop supports the heroic token path from the plan."""
    crusader, growth = _heroic_cards()
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=crusader),
        CardObject(controller_idx=0, owner_idx=0, card_info=growth),
    ]
    game.action_cast(0)
    target = game.state.zones.creatures_of(0)[0]
    data = game.action_cast(0, target_uid=str(target.obj_id))
    names = [perm["name"] for perm in data["playerBattlefield"]]
    assert "Akroan Crusader" in names
    assert "Soldier Token" in names


def test_heroic_trigger_uses_stack_before_targeting_spell_resolves():
    """Heroic token creation resolves from a trigger above the targeting spell."""
    crusader, growth = _heroic_cards()
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=crusader),
        CardObject(controller_idx=0, owner_idx=0, card_info=growth),
    ]
    game.action_cast(0)
    target = game.state.zones.creatures_of(0)[0]

    data = game.action_cast_to_stack(0, target_uid=str(target.obj_id))

    assert data["stack"][0]["type"] == "TriggeredAbilityOnStack"
    assert data["stack"][1]["name"] == "Titan's Strength"
    game.action_pass_priority()
    data = game.action_pass_priority()
    names = [perm["name"] for perm in data["playerBattlefield"]]
    assert "Soldier Token" in names
    assert data["stack"][0]["name"] == "Titan's Strength"


def test_prowess_trigger_uses_stack_above_noncreature_spell():
    """Prowess-style spell triggers are registered from resolved permanents."""
    swiftspear, growth = _prowess_cards()
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=swiftspear),
        CardObject(controller_idx=0, owner_idx=0, card_info=growth),
    ]
    game.action_cast(0)

    data = game.action_cast_to_stack(0)

    assert data["stack"][0]["type"] == "TriggeredAbilityOnStack"
    assert data["stack"][1]["name"] == "Titan's Strength"
    game.action_pass_priority()
    game.action_pass_priority()
    swiftspear_perm = game.state.zones.creatures_of(0)[0]
    assert swiftspear_perm.counters.get("+1/+1") == 1


def test_player_attack_uses_combat_rules_for_unblocked_damage():
    """A confirmed player attack taps the attacker and damages the opponent."""
    memnite = make_card(
        name="Memnite",
        type_line="Artifact Creature — Construct",
        stats=_CardStats(cmc=0.0, pt="1/1"),
        mana_cost="",
    )
    game = create_game([memnite for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    game.action_cast(0)
    attacker = game.state.zones.creatures_of(0)[0]
    attacker.sick = False
    game.action_go_to_attack()
    game.action_toggle_attacker(str(attacker.obj_id))
    data = game.action_confirm_attack()
    assert data["phase"] == "main2"
    assert data["opponentLife"] == 19
    assert data["playerBattlefield"][0]["tapped"]


def test_player_attack_trigger_resolves_before_combat_damage():
    """Attack triggers emitted by the game loop resolve before combat damage."""
    memnite = make_card(
        name="Memnite",
        type_line="Artifact Creature — Construct",
        stats=_CardStats(cmc=0.0, pt="1/1"),
        mana_cost="",
    )
    game = create_game([memnite for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    game.action_cast(0)
    attacker = game.state.zones.creatures_of(0)[0]
    attacker.sick = False
    game.state.trigger_registry.register(
        attacker,
        TriggerKey.ATTACKS,
        TriggerSpec(condition=is_attacks, effect=_GainLifeEffect(player_idx=0, amount=1)),
    )

    game.action_go_to_attack()
    game.action_toggle_attacker(str(attacker.obj_id))
    data = game.action_confirm_attack()

    assert data["playerLife"] == 21
    assert data["opponentLife"] == 19


def test_player_blocker_prevents_opponent_combat_damage():
    """Opponent combat delegates blocker damage and SBA cleanup to combat rules."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    blocker = place_on_battlefield(make_creature("Bear", 2, 2), 0, game.state.zones)
    attacker = place_on_battlefield(make_creature("Goblin", 2, 2), 1, game.state.zones)
    blocker.sick = False
    attacker.sick = False

    data = game.action_end_turn()
    assert data["phase"] == "declare_blockers"
    assert data["opponentAttackers"][0]["tapped"]

    game.action_assign_blocker(str(blocker.obj_id), str(attacker.obj_id))
    data = game.action_confirm_blocks()
    assert data["phase"] == "draw"
    assert data["playerLife"] == 20
    assert blocker not in game.state.zones.battlefield
    assert attacker not in game.state.zones.battlefield


def test_block_trigger_resolves_before_combat_damage():
    """Block triggers emitted by the game loop resolve before combat damage."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    blocker = place_on_battlefield(make_creature("Bear", 2, 2), 0, game.state.zones)
    attacker = place_on_battlefield(make_creature("Goblin", 2, 2), 1, game.state.zones)
    blocker.sick = False
    attacker.sick = False
    game.state.trigger_registry.register(
        blocker,
        TriggerKey.BLOCKS,
        TriggerSpec(condition=is_blocks, effect=_GainLifeEffect(player_idx=0, amount=1)),
    )
    game.action_end_turn()

    game.action_assign_blocker(str(blocker.obj_id), str(attacker.obj_id))
    data = game.action_confirm_blocks()

    assert data["playerLife"] == 21
    assert data["phase"] == "draw"


def test_beginning_of_combat_trigger_resolves_on_attack_step_entry():
    """Beginning-of-combat triggers resolve when the player moves to combat."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    observer = place_on_battlefield(make_creature("Combat Observer", 1, 1), 0, game.state.zones)
    game.state.trigger_registry.register(
        observer,
        TriggerKey.BEGINNING_OF_COMBAT,
        TriggerSpec(
            condition=is_beginning_of_combat,
            effect=_GainLifeEffect(player_idx=0, amount=1),
        ),
    )

    data = game.action_go_to_attack()

    assert data["playerLife"] == 21
    assert data["phase"] == "attack"


def test_end_step_trigger_resolves_when_player_ends_turn():
    """End-step triggers resolve before the opponent turn completes."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    observer = place_on_battlefield(make_creature("End Observer", 1, 1), 0, game.state.zones)
    game.state.trigger_registry.register(
        observer,
        TriggerKey.END_STEP,
        TriggerSpec(condition=is_end_step, effect=_GainLifeEffect(player_idx=0, amount=1)),
    )

    data = game.action_end_turn()

    assert data["playerLife"] == 21
    assert data["phase"] == "draw"


def test_upkeep_trigger_resolves_before_player_draw():
    """Upkeep triggers resolve at the start of the player's next turn."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    observer = place_on_battlefield(make_creature("Upkeep Observer", 1, 1), 0, game.state.zones)
    game.action_end_turn()
    game.state.trigger_registry.register(
        observer,
        TriggerKey.BEGINNING_OF_UPKEEP,
        TriggerSpec(
            condition=is_beginning_of_upkeep,
            effect=_GainLifeEffect(player_idx=0, amount=1),
        ),
    )

    data = game.action_draw()

    assert data["playerLife"] == 21
    assert data["phase"] == "main1"


def test_end_turn_returns_to_player_draw_when_opponent_has_no_attackers():
    """The simple opponent turn advances back to the player's draw phase."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    data = game.action_end_turn()
    assert data["phase"] == "draw"
    assert data["turn"] == 2


def test_opponent_creature_cast_uses_stack_and_resolves():
    """Opponent creature casting uses the same stack-backed pipeline."""
    memnite = make_card(
        name="Memnite",
        type_line="Artifact Creature — Construct",
        stats=_CardStats(cmc=0.0, pt="1/1"),
        mana_cost="",
    )
    game = create_game(make_deck(lands=20), [memnite for _ in range(20)])
    game.action_keep()
    data = game.action_end_turn()
    assert not data["stack"]
    assert len(data["opponentBattlefield"]) == 1
    assert data["opponentBattlefield"][0]["name"] == "Memnite"
    assert any(
        entry["actor"] == "opponent" and entry["detail"] == "Memnite on stack"
        for entry in data["log"]
    )


def test_opponent_burn_cast_uses_stack_and_damages_player():
    """Opponent burn spell resolves through the stack and hits the player."""
    shock = make_card(
        name="Shock",
        type_line="Instant",
        stats=_CardStats(cmc=0.0, pt="0/0"),
        oracle="Shock deals 2 damage to any target.",
        mana_cost="",
    )
    game = create_game(make_deck(lands=20), [shock for _ in range(20)])
    game.action_keep()
    data = game.action_end_turn()
    assert not data["stack"]
    assert data["playerLife"] == 18
    assert "Shock" in data["opponentGraveyard"]


def test_game_session_store_round_trip_and_remove():
    """create_game registers sessions retrievable by FastAPI routes."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game_id = game.to_client()["gameId"]
    assert get_game(game_id) is game
    remove_game(game_id)
    assert get_game(game_id) is None


class _GainLifeEffect(Effect):
    """Test effect that gains life when an ability resolves."""

    def __init__(self, player_idx: int, amount: int) -> None:
        self.player_idx = player_idx
        self.amount = amount

    def resolve(self, game: GameState, _source: GameObject) -> str:
        """Apply the test life gain effect."""
        game.players[self.player_idx].life += self.amount
        return f"Gained {self.amount} life"

    def describe(self) -> str:
        """Return a short description for test diagnostics."""
        return f"Gain {self.amount} life"


def _heroic_cards() -> tuple[CardInfo, CardInfo]:
    """Return a simple heroic creature and a spell that can target it."""
    crusader = make_card(
        name="Akroan Crusader",
        type_line="Creature — Human Soldier",
        stats=_CardStats(cmc=0.0, pt="1/1"),
        oracle=(
            "Heroic — Whenever you cast a spell that targets Akroan Crusader, "
            "create a 1/1 red Soldier creature token."
        ),
        mana_cost="",
    )
    growth = make_card(
        name="Titan's Strength",
        type_line="Instant",
        stats=_CardStats(cmc=0.0, pt="0/0"),
        oracle="Target creature gets +3/+1 until end of turn.",
        mana_cost="",
    )
    return crusader, growth


def _prowess_cards() -> tuple[CardInfo, CardInfo]:
    """Return a simple prowess creature and a noncreature spell."""
    swiftspear = make_card(
        name="Monastery Swiftspear",
        type_line="Creature — Human Monk",
        stats=_CardStats(cmc=0.0, pt="1/2"),
        oracle="Prowess",
        mana_cost="",
    )
    growth = make_card(
        name="Titan's Strength",
        type_line="Instant",
        stats=_CardStats(cmc=0.0, pt="0/0"),
        oracle="Target creature gets +3/+1 until end of turn.",
        mana_cost="",
    )
    return swiftspear, growth
