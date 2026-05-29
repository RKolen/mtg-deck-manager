"""Batch 7: evoke cast, bloodrush, Activate action, 72/72 handlers."""

from __future__ import annotations

from engine.abilities.activated.bloodrush import apply_bloodrush, has_bloodrush
from engine.abilities.keywords.actions.resolve import _HANDLERS, resolve_spell_keyword_actions
from engine.abilities.keywords.actions.resolve import ActionContext
from engine.abilities.keywords.casting.evoke import (
    evoke_mana_needed,
    has_evoke,
    normalize_evoke_cast,
)
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.game.cast_context import CastAnnounceOptions, HandAlternateCastChoices
from engine.game.cast_announce_validate import validate_announce_cast
from tests.conftest import add_to_hand, fresh_game, make_creature, place_on_battlefield


def test_all_seventy_two_keyword_actions_have_handlers():
    """Every Scryfall keyword action has a handler."""
    assert len(_HANDLERS) == 72
    assert 'Activate' in _HANDLERS


def test_evoke_cast_and_sacrifice():
    """Casting for evoke marks the creature and sacrifices on ETB."""
    card_info = make_creature(
        'Mulldrifter',
        2,
        2,
        oracle='Flying\nEvoke {2}{U}',
    )
    assert has_evoke(card_info)
    assert normalize_evoke_cast(card_info, True)
    assert evoke_mana_needed(card_info)[0] >= 1

    game = fresh_game()
    creature = place_on_battlefield(card_info, 0, game.zones)
    creature.counters['evoked'] = 1
    details = apply_etb_other_abilities(game, creature)
    assert any('evoked' in detail for detail in details)
    assert game.zones.find_permanent(creature.obj_id) is None


def test_validate_cast_for_evoke():
    """Announce-cast accepts evoke when the creature has evoke."""
    game = fresh_game()
    card_info = make_creature('Rift', 2, 2, oracle='Evoke {1}{U}')
    paid, err = validate_announce_cast(
        game.zones,
        0,
        card_info,
        CastAnnounceOptions(alternate=HandAlternateCastChoices(cast_for_evoke=True)),
        False,
        None,
        game,
    )
    assert err is None
    assert paid is not None
    assert paid.modifiers.evoke


def test_bloodrush_discards_and_pumps():
    """Bloodrush discards the creature card and pumps the target."""
    game = fresh_game()
    target = place_on_battlefield(make_creature('Gruul', 3, 3), 0, game.zones)
    rush_card = make_creature(
        'Ghor',
        4,
        4,
        oracle='Bloodrush — {R}, Discard Ghor: Target creature gets +4/+0.',
    )
    add_to_hand(rush_card, 0, game.zones)
    assert has_bloodrush(rush_card)
    detail = apply_bloodrush(
        game.zones,
        0,
        0,
        str(target.obj_id),
    )
    assert detail is not None
    assert target.counters.get('+power/+0') == 4
    assert target.counters.get('+1/+1', 0) == 0
    assert len(game.zones.player_zones[0].hand) == 0


def test_activate_keyword_action_taps_target():
    """Activate keyword action taps the target permanent."""
    game = fresh_game()
    target = place_on_battlefield(make_creature('Monolith', 0, 4), 0, game.zones)
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Activate',
        target_creature_uid=str(target.obj_id),
    ))
    assert 'activated' in detail
    assert target.tapped
