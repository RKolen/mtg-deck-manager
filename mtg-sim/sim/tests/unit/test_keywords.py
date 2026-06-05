"""Unit tests for Scryfall keyword registry and keyword hooks (Phase E, 2026)."""

from __future__ import annotations

import pytest

from engine.abilities import keywords
from engine.abilities.keywords.targeting import _SourceTypeFlags
from engine.abilities.keywords.casting import (
    bestow_host_error,
    bestow_mana_needed,
    can_cast_via_flashback,
    cast_mana_with_entwine,
    entwine_cost,
    entwine_mana_needed,
    escape_cost,
    escape_exiles_required,
    escape_mana_needed,
    escape_payment_error,
    exile_for_escape_cost,
    flashback_cost,
    flashback_mana_needed,
    has_bestow,
    has_entwine,
    has_escape,
    has_flashback,
    has_miracle,
    has_overload,
    has_replicate,
    miracle_cost,
    miracle_mana_needed,
    normalize_bestow,
    normalize_entwined,
    normalize_miracle_cast,
    normalize_overloaded,
    normalize_replicate_times,
    overload_hits_each_creature,
    overload_mana_needed,
    replicate_extra_mana,
    replicate_mana_per_time,
    supports_replicate_copies,
)
from engine.abilities.keywords import (
    KEYWORD_ENTRIES,
    SCRYFALL_KEYWORD_COUNT,
    detect_keywords,
    registry_summary,
)
from engine.core.game_object import (
    CardObject,
    SpellOnStack,
    Target,
)
from tests.conftest import (
    fresh_game,
    hexproof_game_setup,
    make_card,
    make_creature,
    make_entwine_charm,
    make_instant,
    place_on_battlefield,
)


def test_registry_matches_scryfall_catalog_size():
    """Registry contains every Scryfall keyword entry (2026 catalog)."""
    assert len(KEYWORD_ENTRIES) == SCRYFALL_KEYWORD_COUNT
    assert SCRYFALL_KEYWORD_COUNT >= 350
    summary = registry_summary()
    assert summary['total'] == SCRYFALL_KEYWORD_COUNT
    assert summary['by_kind']['ability'] >= 200
    assert summary['by_kind']['action'] >= 70
    assert summary['by_kind']['word'] >= 60


def test_detect_keywords_handles_none_oracle():
    """None or empty oracle text returns an empty set without raising."""
    assert detect_keywords(None) == frozenset()
    assert detect_keywords('') == frozenset()


@pytest.mark.parametrize('name,kind,category', KEYWORD_ENTRIES)
def test_each_scryfall_keyword_detects_in_oracle(name: str, kind: str, category: str):
    """Every catalog keyword is detected when present in oracle text."""
    del kind, category
    oracle = f"Reminder text. {name}. Rules text."
    detected = detect_keywords(oracle)
    assert name in detected


def test_cast_action_does_not_false_positive_in_forecast():
    """Keyword action Cast uses word boundaries (not Forecast)."""
    assert 'Cast' not in detect_keywords('Forecast — reveal the top card.')
    assert 'Cast' in detect_keywords('You may cast this card.')


def test_has_keyword_case_insensitive():
    """Keyword detection is case-insensitive."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Drake', oracle='Flying'),
        0,
        game.zones,
    )
    assert keywords.has_keyword(perm, 'flying')
    assert keywords.has_keyword(perm, 'FLYING')


def test_list_keywords_returns_detected_set():
    """list_keywords returns the full detected keyword set."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Knight', 3, 3, oracle='First strike, vigilance'),
        0,
        game.zones,
    )
    found = keywords.list_keywords(perm)
    assert 'First strike' in found
    assert 'Vigilance' in found


def test_haste_creature_enters_unsick():
    """Haste creatures can attack the turn they enter."""
    game = fresh_game()
    hasty = place_on_battlefield(
        make_creature('Goblin', oracle='Haste'),
        0,
        game.zones,
    )
    assert not hasty.sick


def test_non_haste_creature_enters_sick():
    """Creatures without haste have summoning sickness on ETB."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature('Bear'), 0, game.zones)
    assert bear.sick


def test_flash_on_non_instant():
    """Flash grants instant-speed timing to non-instant spells."""
    sorcery = make_card('Comet', type_line='Sorcery', oracle='Flash')
    assert keywords.has_flash(sorcery)


def test_hexproof_blocks_opponent_targeting():
    """Opponents cannot target hexproof permanents."""
    _game, protected = hexproof_game_setup()
    assert not keywords.can_target_permanent(protected, 1)
    assert keywords.can_target_permanent(protected, 0)


def test_shroud_blocks_all_targeting():
    """Shroud prevents any player from targeting the permanent."""
    game = fresh_game()
    hidden = place_on_battlefield(
        make_creature('Veiled', oracle='Shroud'),
        0,
        game.zones,
    )
    assert not keywords.can_target_permanent(hidden, 0)
    assert not keywords.can_target_permanent(hidden, 1)


def test_ward_allows_opponent_to_target():
    """Ward does not use hexproof-style targeting restriction."""
    game = fresh_game()
    warded = place_on_battlefield(
        make_creature('Guardian', oracle='Ward {2}'),
        0,
        game.zones,
    )
    assert keywords.can_target_permanent(warded, 1)


def test_ward_counters_spell_when_cost_not_paid():
    """Ward counters an opponent's spell if they cannot pay {2}."""
    game = fresh_game()
    warded = place_on_battlefield(
        make_creature('Guardian', oracle='Ward {2}'),
        0,
        game.zones,
    )
    spell = SpellOnStack(
        controller_idx=1,
        owner_idx=1,
        targets=[Target(obj_id=warded.obj_id)],
    )
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones, game)
    assert result.fizzled
    assert result.reason == 'ward_not_paid'


def test_ward_spell_resolves_when_cost_paid():
    """Ward allows resolution when the opponent pays {2} from their mana pool."""
    game = fresh_game()
    warded = place_on_battlefield(
        make_creature('Guardian', oracle='Ward {2}'),
        0,
        game.zones,
    )
    game.players[1].mana_pool.add_color('C', 2)
    spell = SpellOnStack(
        controller_idx=1,
        owner_idx=1,
        targets=[Target(obj_id=warded.obj_id)],
    )
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones, game)
    assert not result.fizzled
    assert game.players[1].mana_pool.total() == 0


def test_protection_from_creatures_blocks_creature_sources():
    """Protection from creatures blocks creature spell targeting."""
    game = fresh_game()
    protected = place_on_battlefield(
        make_creature('Paladin', oracle='Protection from creatures'),
        0,
        game.zones,
    )
    creature_source = keywords.protection_source_from_flags(
        _SourceTypeFlags(is_creature=True)
    )
    non_creature = keywords.protection_source_from_flags()
    assert not keywords.can_target_permanent(protected, 1, source=creature_source)
    assert keywords.can_target_permanent(protected, 1, source=non_creature)


def test_protection_from_red_blocks_red_sources():
    """Protection from red blocks red-colored sources."""
    game = fresh_game()
    protected = place_on_battlefield(
        make_creature('Knight', oracle='Protection from red'),
        0,
        game.zones,
    )
    red_bolt = make_instant('Bolt', mana_cost='{R}')
    assert not keywords.can_target_permanent(protected, 1, source_card=red_bolt)
    white_spell = make_instant('Heal', mana_cost='{W}')
    assert keywords.can_target_permanent(protected, 1, source_card=white_spell)


def test_protection_from_red_and_green_blocks_both():
    """Multi-clause protection parses 'and from' follow-ups."""
    game = fresh_game()
    protected = place_on_battlefield(
        make_creature(
            'Warder',
            oracle='Protection from red and from green',
        ),
        0,
        game.zones,
    )
    assert keywords.protection_qualities(protected) == frozenset({'red', 'green'})
    assert not keywords.can_target_permanent(
        protected, 1, source_card=make_instant('Bolt', mana_cost='{R}'),
    )
    assert not keywords.can_target_permanent(
        protected, 1, source_card=make_instant('Growth', mana_cost='{G}'),
    )
    assert keywords.can_target_permanent(
        protected, 1, source_card=make_instant('Counter', mana_cost='{U}'),
    )


def test_protection_from_instants_blocks_instant_spells():
    """Protection from instants blocks instant spell sources."""
    game = fresh_game()
    protected = place_on_battlefield(
        make_creature('Shell', oracle='Protection from instants'),
        0,
        game.zones,
    )
    assert not keywords.can_target_permanent(
        protected, 1, source_card=make_instant('Shock'),
    )
    assert keywords.can_target_permanent(
        protected, 1, source_card=make_creature('Bear'),
    )


def test_protection_from_colored_blocks_colored_spells():
    """Protection from colored blocks any spell with colored mana in its cost."""
    game = fresh_game()
    protected = place_on_battlefield(
        make_creature('Pale', oracle='Protection from colored'),
        0,
        game.zones,
    )
    assert not keywords.can_target_permanent(
        protected, 1, source_card=make_instant('Bolt', mana_cost='{R}'),
    )
    assert keywords.can_target_permanent(
        protected, 1,
        source_card=make_card('Rock', type_line='Artifact', mana_cost='{2}'),
    )


def test_protection_from_everything_blocks_all_sources():
    """Protection from everything blocks any spell source."""
    game = fresh_game()
    protected = place_on_battlefield(
        make_creature('True Believer', oracle='Protection from everything'),
        0,
        game.zones,
    )
    assert not keywords.can_target_permanent(
        protected, 1, source_card=make_instant('Shock', mana_cost='{R}'),
    )
    assert not keywords.can_target_permanent(
        protected, 1, source_card=make_creature('Bear'),
    )


def test_protection_spell_fizzles_on_stack():
    """A red instant targeting protection-from-red fizzles at resolution."""
    game = fresh_game()
    protected = place_on_battlefield(
        make_creature('Knight', oracle='Protection from red'),
        0,
        game.zones,
    )
    bolt = make_instant('Bolt', mana_cost='{R}')
    source = CardObject(controller_idx=1, owner_idx=1, card_info=bolt)
    spell = SpellOnStack(
        controller_idx=1,
        owner_idx=1,
        source=source,
        targets=[Target(obj_id=protected.obj_id)],
    )
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones)
    assert result.fizzled
    assert result.reason == 'all_targets_illegal'


def test_has_flashback_parses_alternate_cost():
    """Flashback cost is parsed from oracle text."""
    card = make_instant('Ray', oracle='Flashback {2}{R}\nDeal 3 damage.')
    assert has_flashback(card)
    cost = flashback_cost(card)
    assert cost is not None
    assert cost.mana_value == 3
    assert flashback_mana_needed(card) == 3


def test_has_escape_parses_cost_and_exile_count():
    """Escape mana cost and graveyard exile count parse from oracle text."""
    card = make_instant(
        'Scream',
        oracle=(
            'Scream deals 2 damage to any target.\n'
            'Escape—{R}{R}, Exile two other cards from your graveyard.'
        ),
    )
    assert has_escape(card)
    cost = escape_cost(card)
    assert cost is not None
    assert cost.mana_value == 2
    assert escape_exiles_required(card) == 2
    assert escape_mana_needed(card) == 2


def test_exile_for_escape_cost_removes_other_graveyard_cards():
    """Escape exiles the chosen other cards before the spell leaves the graveyard."""
    game = fresh_game()
    spell_info = make_instant(
        'Scream',
        oracle='Escape—{0}\nExile two other cards from your graveyard.',
    )
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=spell_info)
    filler_a = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('A'))
    filler_b = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('B'))
    game.zones.player_zones[0].graveyard.extend([spell, filler_a, filler_b])
    assert escape_payment_error(game.zones, 0, 0, [1, 2], spell_info) is None
    exiled = exile_for_escape_cost(game.zones, 0, [1, 2], spell_info)
    assert exiled == [1, 2]
    assert len(game.zones.player_zones[0].exile) == 2
    assert spell in game.zones.player_zones[0].graveyard


def test_can_cast_via_flashback_allows_instant_timing():
    """Flashback may be cast during combat steps like an instant."""
    card = make_instant('Ray', oracle='Flashback {0}')
    assert can_cast_via_flashback(card, 'attack', stack_is_empty=False)
    assert not can_cast_via_flashback(card, 'upkeep', stack_is_empty=True)


def test_has_miracle_parses_alternate_cost():
    """Miracle cost replaces the mana cost when cast for miracle."""
    card = make_instant(
        'Temporal Mastery',
        cmc=5,
        oracle='Take an extra turn. Miracle {1}{U}',
    )
    assert has_miracle(card)
    cost = miracle_cost(card)
    assert cost is not None
    assert cost.mana_value == 2
    assert miracle_mana_needed(card) == (2, 0)
    assert normalize_miracle_cast(card, True)


def test_replicate_cost_and_copy_support():
    """Replicate adds mana per payment and supports noncreature copies."""
    card = make_instant('Shock', oracle='Shock deals 2 damage. Replicate {0}')
    assert has_replicate(card)
    assert replicate_mana_per_time(card) == 0
    assert normalize_replicate_times(card, 2) == 2
    assert replicate_extra_mana(card, 2) == 0
    assert supports_replicate_copies(card)
    assert not supports_replicate_copies(make_creature('Bear', oracle='Replicate {1}'))


def test_has_overload_parses_alternate_cost():
    """Overload cost replaces the mana cost when paid."""
    card = make_instant(
        'Mortars',
        cmc=2,
        oracle='Mortars deals 4 damage to target creature. Overload {4}',
    )
    assert has_overload(card)
    assert overload_mana_needed(card) == (4, 0)
    assert normalize_overloaded(card, True)
    assert not overload_hits_each_creature(card)
    assert overload_hits_each_creature(
        make_instant('Sweep', oracle='Overload {2}\nDamage each creature.'),
    )


def test_has_bestow_parses_cost_and_validates_host():
    """Bestow cost parses and requires a creature host you control."""
    game = fresh_game()
    spirit = make_creature('Spirit', oracle='Flying\nBestow {2}')
    host = place_on_battlefield(make_creature('Soldier'), 0, game.zones)
    assert has_bestow(spirit)
    assert bestow_mana_needed(spirit) == (2, 0)
    assert normalize_bestow(spirit, str(host.obj_id))
    assert bestow_host_error(game.zones, 0, str(host.obj_id)) is None


def test_has_entwine_parses_cost_and_cast_mana():
    """Entwine cost parses and adds to the base cast mana when paid."""
    card = make_entwine_charm('{2}')
    assert has_entwine(card)
    cost = entwine_cost(card)
    assert cost is not None
    assert cost.mana_value == 2
    assert entwine_mana_needed(card) == 2
    assert normalize_entwined(card, True)
    assert not normalize_entwined(card, False)
    assert cast_mana_with_entwine(card, 0, 0, True) == (2, 0)
