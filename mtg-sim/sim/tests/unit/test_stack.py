"""Unit tests for engine/rules/stack.py."""

from engine.core.game_object import (
    CardObject,
    Effect,
    SpellOnStack,
    Target,
    TriggeredAbilityOnStack,
)
from engine.rules.stack import Stack
from tests.conftest import fresh_game, make_card, make_creature, place_on_battlefield


# ---------------------------------------------------------------------------
# Basic stack operations
# ---------------------------------------------------------------------------

def test_stack_starts_empty():
    """A new Stack has no objects and is_empty is True."""
    s = Stack()
    assert s.is_empty
    assert s.top is None


def test_push_makes_stack_non_empty():
    """Pushing one object makes is_empty False."""
    s = Stack()
    s.push(_make_spell("Lightning Bolt"))
    assert not s.is_empty


def test_top_returns_most_recently_pushed():
    """top returns the last-pushed object (LIFO order)."""
    s = Stack()
    spell1 = _make_spell("Spell A")
    spell2 = _make_spell("Spell B")
    s.push(spell1)
    s.push(spell2)
    assert s.top is spell2


def test_top_does_not_remove_object():
    """Accessing top is non-destructive; the stack remains non-empty."""
    s = Stack()
    s.push(_make_spell("X"))
    _ = s.top
    assert not s.is_empty


def test_resolve_top_pops_object():
    """resolve_top removes the top object, leaving the stack empty."""
    game = fresh_game()
    game.stack.push(_make_spell("Test"))
    game.stack.resolve_top(game.zones)
    assert game.stack.is_empty


def test_resolve_empty_stack_fizzles():
    """resolve_top on an empty stack returns fizzled=True with reason 'stack_empty'."""
    game = fresh_game()
    result = game.stack.resolve_top(game.zones)
    assert result.fizzled
    assert result.reason == "stack_empty"
    assert result.obj is None


# ---------------------------------------------------------------------------
# Resolution — no targets
# ---------------------------------------------------------------------------

def test_no_target_spell_resolves():
    """A spell with no declared targets always resolves (no fizzle check needed)."""
    game = fresh_game()
    spell = _make_spell("Divination", targets=[])
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones)
    assert not result.fizzled
    assert result.obj is spell


# ---------------------------------------------------------------------------
# Resolution — target legality (fizzle rule CR 608.2b)
# ---------------------------------------------------------------------------

def test_permanent_target_legal_resolves():
    """A spell targeting a permanent still on the battlefield resolves normally."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature(), 0, game.zones)
    spell = _make_spell("Shock", targets=[Target(obj_id=bear.obj_id)])
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones)
    assert not result.fizzled


def test_permanent_target_left_battlefield_fizzles():
    """A spell fizzles when its target is no longer on the battlefield (CR 608.2b)."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature(), 0, game.zones)
    spell = _make_spell("Shock", targets=[Target(obj_id=bear.obj_id)])
    game.stack.push(spell)
    game.zones.battlefield.remove(bear)
    result = game.stack.resolve_top(game.zones)
    assert result.fizzled
    assert result.reason == "all_targets_illegal"


def test_fizzled_spell_goes_to_graveyard():
    """When a spell fizzles, its source card is placed in its owner's graveyard."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature(), 0, game.zones)
    card_obj = CardObject(controller_idx=0, owner_idx=0, card_info=make_card("Shock"))
    spell = SpellOnStack(
        controller_idx=0,
        owner_idx=0,
        source=card_obj,
        targets=[Target(obj_id=bear.obj_id)],
    )
    game.stack.push(spell)
    game.zones.battlefield.remove(bear)
    game.stack.resolve_top(game.zones)
    assert card_obj in game.zones.player_zones[0].graveyard


def test_player_target_always_legal():
    """A player target is always legal regardless of board state."""
    game = fresh_game()
    spell = _make_spell("Shock", targets=[Target(player_idx=1)])
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones)
    assert not result.fizzled


def test_one_legal_one_illegal_target_resolves():
    """Fizzle only occurs when ALL targets are illegal; one legal target is enough (CR 608.2b)."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature(), 0, game.zones)
    spell = _make_spell("Electrolyze", targets=[
        Target(obj_id=bear.obj_id),
        Target(player_idx=1),
    ])
    game.stack.push(spell)
    game.zones.battlefield.remove(bear)
    result = game.stack.resolve_top(game.zones)
    assert not result.fizzled


# ---------------------------------------------------------------------------
# Triggered abilities on the stack
# ---------------------------------------------------------------------------

def test_triggered_ability_resolves():
    """A triggered ability with no targets resolves normally."""
    game = fresh_game()
    trig = TriggeredAbilityOnStack(
        controller_idx=0,
        owner_idx=0,
        source_permanent_id=999,
        trigger_key="enters_battlefield",
    )
    game.stack.push(trig)
    result = game.stack.resolve_top(game.zones)
    assert not result.fizzled


def test_triggered_ability_fizzle_does_not_add_to_graveyard():
    """Ability objects have no source card; fizzle produces nothing in the graveyard."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature(), 0, game.zones)
    trig = TriggeredAbilityOnStack(
        controller_idx=0,
        owner_idx=0,
        source_permanent_id=999,
        trigger_key="dies",
        targets=[Target(obj_id=bear.obj_id)],
    )
    game.stack.push(trig)
    game.zones.battlefield.remove(bear)
    result = game.stack.resolve_top(game.zones)
    assert result.fizzled
    assert len(game.zones.player_zones[0].graveyard) == 0


# ---------------------------------------------------------------------------
# counter_top
# ---------------------------------------------------------------------------

def test_counter_top_removes_object():
    """counter_top pops and returns the top object without resolving it."""
    game = fresh_game()
    card_obj = CardObject(controller_idx=1, owner_idx=1, card_info=make_card("Giant Growth"))
    spell = SpellOnStack(controller_idx=1, owner_idx=1, source=card_obj)
    game.stack.push(spell)
    countered = game.stack.counter_top(game.zones)
    assert countered is spell
    assert game.stack.is_empty


def test_counter_top_moves_spell_to_graveyard():
    """Countered spells are placed in their owner's graveyard."""
    game = fresh_game()
    card_obj = CardObject(controller_idx=1, owner_idx=1, card_info=make_card("Doom Blade"))
    spell = SpellOnStack(controller_idx=1, owner_idx=1, source=card_obj)
    game.stack.push(spell)
    game.stack.counter_top(game.zones)
    assert card_obj in game.zones.player_zones[1].graveyard


def test_counter_empty_stack_returns_none():
    """counter_top on an empty stack returns None without raising."""
    game = fresh_game()
    assert game.stack.counter_top(game.zones) is None


# ---------------------------------------------------------------------------
# to_client serialisation
# ---------------------------------------------------------------------------

def test_to_client_top_first():
    """to_client lists the most recently pushed object first."""
    game = fresh_game()
    game.stack.push(_make_spell("Bolt"))
    game.stack.push(_make_spell("Counterspell"))
    data = game.stack.to_client()
    assert data[0]["name"] == "Counterspell"
    assert data[1]["name"] == "Bolt"


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _make_spell(name: str, targets: list[Target] | None = None) -> SpellOnStack:
    """Build a minimal SpellOnStack for testing."""
    card_obj = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_card(name),
    )
    return SpellOnStack(
        controller_idx=0,
        owner_idx=0,
        source=card_obj,
        effect=Effect(),
        targets=targets or [],
    )
