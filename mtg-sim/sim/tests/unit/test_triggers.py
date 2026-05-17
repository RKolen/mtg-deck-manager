"""Unit tests for engine/rules/triggers.py."""

from engine.core.game_object import Target, TriggeredAbilityOnStack
from engine.core.game_state import GameState
from engine.core.turn_structure import Step
from engine.core.zones import Zone
from engine.rules.triggers import TriggerKey, is_attacks, is_beginning_of_combat
from engine.rules.triggers import is_beginning_of_upkeep, is_blocks, is_dies
from engine.rules.triggers import is_draws_card, is_end_step, is_enters_battlefield
from engine.rules.triggers import is_controller_gains_life, is_leaves_battlefield
from engine.rules.triggers import is_deals_combat_damage, is_life_gained
from engine.rules.triggers import is_noncreature_nonland_spell_cast
from engine.rules.triggers import is_spell_cast, is_spell_targeting_source
from engine.rules.triggers import is_source_deals_combat_damage
from engine.rules.triggers import spell_cast_event
from tests.conftest import add_to_hand, add_to_library, fresh_game, make_card
from tests.conftest import make_creature, make_instant, place_on_battlefield


def test_etb_trigger_goes_on_stack_from_game_state_listener():
    """A registered ETB trigger fires from GameState's zone listener."""
    game = fresh_game()
    soul_warden = place_on_battlefield(
        make_creature("Soul Warden", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        soul_warden,
        TriggerKey.ENTERS_BATTLEFIELD,
        is_enters_battlefield,
    )

    place_on_battlefield(make_creature("Bear", 2, 2), 1, game.zones)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == soul_warden.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.ENTERS_BATTLEFIELD.value


def test_etb_condition_ignores_non_battlefield_moves():
    """ETB conditions do not fire for unrelated zone moves."""
    game = fresh_game()
    soul_warden = place_on_battlefield(
        make_creature("Soul Warden", 1, 1),
        0,
        game.zones,
    )
    bear = place_on_battlefield(make_creature("Bear", 2, 2), 1, game.zones)
    game.trigger_registry.register(
        soul_warden,
        TriggerKey.ENTERS_BATTLEFIELD,
        is_enters_battlefield,
    )

    game.zones.leave_battlefield(bear, Zone.GRAVEYARD, "destroy")

    assert game.stack.top is None


def test_simultaneous_triggers_are_stacked_in_apnap_order():
    """Non-active player's trigger is on top after APNAP stack ordering."""
    game = fresh_game()
    opponent_observer = place_on_battlefield(
        make_creature("Opponent Observer", 1, 1),
        1,
        game.zones,
    )
    player_observer = place_on_battlefield(
        make_creature("Player Observer", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        opponent_observer,
        TriggerKey.ENTERS_BATTLEFIELD,
        is_enters_battlefield,
    )
    game.trigger_registry.register(
        player_observer,
        TriggerKey.ENTERS_BATTLEFIELD,
        is_enters_battlefield,
    )

    place_on_battlefield(make_creature("Bear", 2, 2), 0, game.zones)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == opponent_observer.obj_id
    assert trigger.controller_idx == 1


def test_trigger_does_not_fire_after_source_left_battlefield():
    """Registered triggers stop firing when their source permanent is gone."""
    game = fresh_game()
    soul_warden = place_on_battlefield(
        make_creature("Soul Warden", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        soul_warden,
        TriggerKey.ENTERS_BATTLEFIELD,
        is_enters_battlefield,
    )
    game.zones.leave_battlefield(soul_warden, Zone.GRAVEYARD, "destroy")

    place_on_battlefield(make_creature("Bear", 2, 2), 1, game.zones)

    assert game.stack.top is None


def test_dies_trigger_goes_on_stack_from_sba_death():
    """A registered dies trigger fires when a creature dies from SBAs."""
    game = fresh_game()
    blood_artist = place_on_battlefield(
        make_creature("Blood Artist", 0, 1),
        0,
        game.zones,
    )
    bear = place_on_battlefield(make_creature("Bear", 2, 2), 1, game.zones)
    game.trigger_registry.register(blood_artist, TriggerKey.DIES, is_dies)

    bear.damage_marked = 2
    game.check_sbas()

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == blood_artist.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.DIES.value


def test_self_dies_trigger_fires_from_own_sba_death():
    """Dies triggers can fire from the source permanent leaving battlefield."""
    game = fresh_game()
    doomed = place_on_battlefield(
        make_creature("Doomed Traveler", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(doomed, TriggerKey.DIES, is_dies)

    doomed.damage_marked = 1
    game.check_sbas()

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == doomed.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.DIES.value


def test_leaves_battlefield_trigger_goes_on_stack_from_destroy():
    """A registered leaves-battlefield trigger fires when a permanent leaves."""
    game = fresh_game()
    watcher = place_on_battlefield(
        make_creature("Departures Watcher", 1, 1),
        0,
        game.zones,
    )
    bear = place_on_battlefield(make_creature("Bear", 2, 2), 1, game.zones)
    game.trigger_registry.register(
        watcher,
        TriggerKey.LEAVES_BATTLEFIELD,
        is_leaves_battlefield,
    )

    game.zones.leave_battlefield(bear, Zone.GRAVEYARD, "destroy")

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == watcher.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.LEAVES_BATTLEFIELD.value


def test_self_leaves_battlefield_trigger_fires_from_own_departure():
    """Leaves-battlefield triggers can fire from the source permanent leaving."""
    game = fresh_game()
    traveler = place_on_battlefield(
        make_creature("Selfless Spirit", 2, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        traveler,
        TriggerKey.LEAVES_BATTLEFIELD,
        is_leaves_battlefield,
    )

    game.zones.leave_battlefield(traveler, Zone.GRAVEYARD, "destroy")

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == traveler.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.LEAVES_BATTLEFIELD.value


def test_leaves_battlefield_trigger_ignores_non_battlefield_moves():
    """Leaves-battlefield triggers require an object to leave the battlefield."""
    game = fresh_game()
    watcher = place_on_battlefield(
        make_creature("Departures Watcher", 1, 1),
        0,
        game.zones,
    )
    card = add_to_library(make_card("Drawn Card"), 0, game.zones)
    game.trigger_registry.register(
        watcher,
        TriggerKey.LEAVES_BATTLEFIELD,
        is_leaves_battlefield,
    )

    game.zones.draw(card.controller_idx)

    assert game.stack.top is None


def test_upkeep_trigger_goes_on_stack_from_step_event():
    """Beginning-of-upkeep triggers fire from explicit step events."""
    game = fresh_game()
    shrine = place_on_battlefield(
        make_creature("Shrine Keeper", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        shrine,
        TriggerKey.BEGINNING_OF_UPKEEP,
        is_beginning_of_upkeep,
    )

    game.fire_step_triggers(Step.UPKEEP)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == shrine.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.BEGINNING_OF_UPKEEP.value


def test_upkeep_trigger_does_not_fire_during_draw_step():
    """Beginning-of-upkeep triggers ignore other beginning-phase steps."""
    game = fresh_game()
    shrine = place_on_battlefield(
        make_creature("Shrine Keeper", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        shrine,
        TriggerKey.BEGINNING_OF_UPKEEP,
        is_beginning_of_upkeep,
    )

    game.fire_step_triggers(Step.DRAW)

    assert game.stack.top is None


def test_beginning_of_combat_trigger_goes_on_stack_from_step_event():
    """Beginning-of-combat triggers fire from explicit step events."""
    game = fresh_game()
    captain = place_on_battlefield(
        make_creature("Battle Captain", 2, 2),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        captain,
        TriggerKey.BEGINNING_OF_COMBAT,
        is_beginning_of_combat,
    )

    game.fire_step_triggers(Step.BEGIN_COMBAT)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == captain.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.BEGINNING_OF_COMBAT.value


def test_beginning_of_combat_trigger_does_not_fire_during_upkeep():
    """Beginning-of-combat triggers ignore other beginning steps."""
    game = fresh_game()
    captain = place_on_battlefield(
        make_creature("Battle Captain", 2, 2),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        captain,
        TriggerKey.BEGINNING_OF_COMBAT,
        is_beginning_of_combat,
    )

    game.fire_step_triggers(Step.UPKEEP)

    assert game.stack.top is None


def test_end_step_trigger_goes_on_stack_from_step_event():
    """End-step triggers fire from explicit step events."""
    game = fresh_game()
    oracle = place_on_battlefield(
        make_creature("End Step Oracle", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        oracle,
        TriggerKey.END_STEP,
        is_end_step,
    )

    game.fire_step_triggers(Step.END_STEP)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == oracle.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.END_STEP.value


def test_end_step_trigger_does_not_fire_during_cleanup():
    """End-step triggers ignore cleanup."""
    game = fresh_game()
    oracle = place_on_battlefield(
        make_creature("End Step Oracle", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        oracle,
        TriggerKey.END_STEP,
        is_end_step,
    )

    game.fire_step_triggers(Step.CLEANUP)

    assert game.stack.top is None


def test_draw_card_trigger_goes_on_stack_from_draw_event():
    """Draw-card triggers fire from library-to-hand draw events."""
    game = fresh_game()
    observer = place_on_battlefield(
        make_creature("Draw Observer", 1, 1),
        0,
        game.zones,
    )
    add_to_library(make_card("Drawn Card"), 0, game.zones)
    game.trigger_registry.register(observer, TriggerKey.DRAWS_CARD, is_draws_card)

    game.zones.draw(0)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == observer.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.DRAWS_CARD.value


def test_draw_card_trigger_does_not_fire_from_draw_step_event():
    """Draw-card triggers require an actual card draw event."""
    game = fresh_game()
    observer = place_on_battlefield(
        make_creature("Draw Observer", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(observer, TriggerKey.DRAWS_CARD, is_draws_card)

    game.fire_step_triggers(Step.DRAW)

    assert game.stack.top is None


def test_life_gained_trigger_goes_on_stack_from_gain_life():
    """Life-gain triggers fire from GameState.gain_life."""
    game = fresh_game()
    observer = place_on_battlefield(
        make_creature("Life Observer", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(observer, TriggerKey.LIFE_GAINED, is_life_gained)

    game.gain_life(1, 3)

    trigger = _top_trigger(game)
    assert game.players[1].life == 23
    assert trigger.source_permanent_id == observer.obj_id
    assert trigger.trigger_key == TriggerKey.LIFE_GAINED.value


def test_controller_gains_life_trigger_ignores_opponents_life_gain():
    """Controller-specific life-gain triggers only fire for their controller."""
    game = fresh_game()
    observer = place_on_battlefield(
        make_creature("Life Observer", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        observer,
        TriggerKey.LIFE_GAINED,
        is_controller_gains_life,
    )

    game.gain_life(1, 3)

    assert game.stack.top is None


def test_life_gained_trigger_ignores_zero_life_gain():
    """Zero or negative life gain is not a life-gain event."""
    game = fresh_game()
    observer = place_on_battlefield(
        make_creature("Life Observer", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(observer, TriggerKey.LIFE_GAINED, is_life_gained)

    game.gain_life(0, 0)

    assert game.players[0].life == 20
    assert game.stack.top is None


def test_combat_damage_trigger_goes_on_stack_from_damage_event():
    """Combat-damage triggers fire from explicit combat damage events."""
    game = fresh_game()
    observer = place_on_battlefield(
        make_creature("Damage Observer", 1, 1),
        0,
        game.zones,
    )
    attacker = place_on_battlefield(make_creature("Goblin", 2, 2), 0, game.zones)
    game.trigger_registry.register(
        observer,
        TriggerKey.DEALS_COMBAT_DAMAGE,
        is_deals_combat_damage,
    )

    game.fire_combat_damage_triggers(attacker, 2, damaged_player_idx=1)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == observer.obj_id
    assert trigger.trigger_key == TriggerKey.DEALS_COMBAT_DAMAGE.value


def test_source_deals_combat_damage_trigger_ignores_other_sources():
    """Source-specific combat-damage triggers only fire for their own source."""
    game = fresh_game()
    watched = place_on_battlefield(make_creature("Watched", 2, 2), 0, game.zones)
    other = place_on_battlefield(make_creature("Other", 2, 2), 0, game.zones)
    game.trigger_registry.register(
        watched,
        TriggerKey.DEALS_COMBAT_DAMAGE,
        is_source_deals_combat_damage,
    )

    game.fire_combat_damage_triggers(other, 2, damaged_player_idx=1)

    assert game.stack.top is None


def test_combat_damage_trigger_ignores_zero_damage():
    """Zero combat damage is not a damage event."""
    game = fresh_game()
    observer = place_on_battlefield(
        make_creature("Damage Observer", 1, 1),
        0,
        game.zones,
    )
    attacker = place_on_battlefield(make_creature("Goblin", 2, 2), 0, game.zones)
    game.trigger_registry.register(
        observer,
        TriggerKey.DEALS_COMBAT_DAMAGE,
        is_deals_combat_damage,
    )

    game.fire_combat_damage_triggers(attacker, 0, damaged_player_idx=1)

    assert game.stack.top is None


def test_spell_cast_trigger_goes_on_stack_from_cast_event():
    """Spell-cast triggers fire from explicit cast events."""
    game = fresh_game()
    observer = place_on_battlefield(
        make_creature("Cast Observer", 1, 1),
        0,
        game.zones,
    )
    spell = add_to_hand(make_instant("Lightning Bolt"), 0, game.zones)
    game.trigger_registry.register(observer, TriggerKey.SPELL_CAST, is_spell_cast)

    game.fire_spell_cast_triggers(spell)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == observer.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.SPELL_CAST.value


def test_spell_cast_event_carries_spell_targets():
    """Spell-cast events keep target choices for heroic-style conditions."""
    spell = add_to_hand(make_instant("Titan's Strength"), 0, fresh_game().zones)
    target = Target(obj_id=123)

    event = spell_cast_event(spell, (target,))

    assert event.targets == (target,)


def test_spell_cast_trigger_does_not_fire_from_draw_event():
    """Spell-cast triggers ignore unrelated zone movement events."""
    game = fresh_game()
    observer = place_on_battlefield(
        make_creature("Cast Observer", 1, 1),
        0,
        game.zones,
    )
    add_to_library(make_card("Drawn Card"), 0, game.zones)
    game.trigger_registry.register(observer, TriggerKey.SPELL_CAST, is_spell_cast)

    game.zones.draw(0)

    assert game.stack.top is None


def test_noncreature_nonland_spell_cast_trigger_fires_for_own_instant():
    """Prowess-style conditions fire for your noncreature nonland spell."""
    game = fresh_game()
    prowess_creature = place_on_battlefield(
        make_creature("Monastery Swiftspear", 1, 2),
        0,
        game.zones,
    )
    spell = add_to_hand(make_instant("Titan's Strength"), 0, game.zones)
    game.trigger_registry.register(
        prowess_creature,
        TriggerKey.SPELL_CAST,
        is_noncreature_nonland_spell_cast,
    )

    game.fire_spell_cast_triggers(spell)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == prowess_creature.obj_id
    assert trigger.trigger_key == TriggerKey.SPELL_CAST.value


def test_noncreature_nonland_spell_cast_trigger_ignores_creatures():
    """Prowess-style conditions ignore creature spells."""
    game = fresh_game()
    prowess_creature = place_on_battlefield(
        make_creature("Monastery Swiftspear", 1, 2),
        0,
        game.zones,
    )
    spell = add_to_hand(make_creature("Bear", 2, 2), 0, game.zones)
    game.trigger_registry.register(
        prowess_creature,
        TriggerKey.SPELL_CAST,
        is_noncreature_nonland_spell_cast,
    )

    game.fire_spell_cast_triggers(spell)

    assert game.stack.top is None


def test_noncreature_nonland_spell_cast_trigger_ignores_opponents_spells():
    """Prowess-style conditions only fire for the source controller's spells."""
    game = fresh_game()
    prowess_creature = place_on_battlefield(
        make_creature("Monastery Swiftspear", 1, 2),
        0,
        game.zones,
    )
    spell = add_to_hand(make_instant("Lightning Bolt"), 1, game.zones)
    game.trigger_registry.register(
        prowess_creature,
        TriggerKey.SPELL_CAST,
        is_noncreature_nonland_spell_cast,
    )

    game.fire_spell_cast_triggers(spell)

    assert game.stack.top is None


def test_spell_targeting_source_trigger_fires_for_own_targeted_spell():
    """Heroic-style conditions fire when your spell targets the source permanent."""
    game = fresh_game()
    heroic_creature = place_on_battlefield(
        make_creature("Akroan Crusader", 1, 1),
        0,
        game.zones,
    )
    spell = add_to_hand(make_instant("Titan's Strength"), 0, game.zones)
    game.trigger_registry.register(
        heroic_creature,
        TriggerKey.SPELL_CAST,
        is_spell_targeting_source,
    )

    game.fire_spell_cast_triggers(spell, (Target(obj_id=heroic_creature.obj_id),))

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == heroic_creature.obj_id
    assert trigger.trigger_key == TriggerKey.SPELL_CAST.value


def test_spell_targeting_source_trigger_ignores_other_targets():
    """Heroic-style conditions ignore spells that target a different permanent."""
    game = fresh_game()
    heroic_creature = place_on_battlefield(
        make_creature("Akroan Crusader", 1, 1),
        0,
        game.zones,
    )
    other_creature = place_on_battlefield(make_creature("Bear", 2, 2), 0, game.zones)
    spell = add_to_hand(make_instant("Titan's Strength"), 0, game.zones)
    game.trigger_registry.register(
        heroic_creature,
        TriggerKey.SPELL_CAST,
        is_spell_targeting_source,
    )

    game.fire_spell_cast_triggers(spell, (Target(obj_id=other_creature.obj_id),))

    assert game.stack.top is None


def test_attack_trigger_goes_on_stack_from_declared_attacker():
    """Attack triggers fire when an attacker is declared."""
    game = fresh_game()
    raider = place_on_battlefield(
        make_creature("Raid Captain", 2, 2),
        0,
        game.zones,
    )
    attacker = place_on_battlefield(
        make_creature("Goblin", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(raider, TriggerKey.ATTACKS, is_attacks)

    game.fire_attack_triggers(attacker)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == raider.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.ATTACKS.value


def test_attack_trigger_does_not_fire_from_upkeep_event():
    """Attack triggers ignore unrelated step events."""
    game = fresh_game()
    raider = place_on_battlefield(
        make_creature("Raid Captain", 2, 2),
        0,
        game.zones,
    )
    game.trigger_registry.register(raider, TriggerKey.ATTACKS, is_attacks)

    game.fire_step_triggers(Step.UPKEEP)

    assert game.stack.top is None


def test_block_trigger_goes_on_stack_from_declared_blocker():
    """Block triggers fire when a blocker is declared."""
    game = fresh_game()
    sentry = place_on_battlefield(
        make_creature("Sentry", 1, 4),
        0,
        game.zones,
    )
    blocker = place_on_battlefield(
        make_creature("Wall", 0, 4),
        0,
        game.zones,
    )
    attacker = place_on_battlefield(
        make_creature("Goblin", 2, 2),
        1,
        game.zones,
    )
    game.trigger_registry.register(sentry, TriggerKey.BLOCKS, is_blocks)

    game.fire_block_triggers(blocker, attacker)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == sentry.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.BLOCKS.value


def test_block_trigger_does_not_fire_from_attack_event():
    """Block triggers ignore attack declaration events."""
    game = fresh_game()
    sentry = place_on_battlefield(
        make_creature("Sentry", 1, 4),
        0,
        game.zones,
    )
    attacker = place_on_battlefield(
        make_creature("Goblin", 2, 2),
        1,
        game.zones,
    )
    game.trigger_registry.register(sentry, TriggerKey.BLOCKS, is_blocks)

    game.fire_attack_triggers(attacker)

    assert game.stack.top is None


def _top_trigger(game: GameState) -> TriggeredAbilityOnStack:
    """Return the stack top narrowed for Pylance."""
    trigger = game.stack.top
    assert isinstance(trigger, TriggeredAbilityOnStack)
    return trigger
