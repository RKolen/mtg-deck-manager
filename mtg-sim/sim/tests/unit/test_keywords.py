"""Unit tests for Scryfall keyword registry and keyword hooks (Phase E, 2026)."""

from __future__ import annotations

import pytest

from engine.abilities import activated, keywords
from engine.abilities.keywords.casting import (
    can_cast_via_escape,
    can_cast_via_flashback,
    aftermath_mana_needed,
    can_cast_aftermath,
    can_cast_via_retrace,
    can_cast_via_jump_start,
    discard_land_for_retrace,
    has_retrace,
    retrace_land_discard_error,
    retrace_mana_needed,
    has_aftermath,
    discard_for_jump_start,
    has_jump_start,
    jump_start_cost,
    jump_start_discard_error,
    jump_start_mana_needed,
    buyback_cost,
    buyback_extra_mana,
    buyback_mana_needed,
    cast_mana_needed,
    has_buyback,
    normalize_buyback,
    cast_mana_with_entwine,
    entwine_cost,
    entwined_extra_draw,
    has_entwine,
    normalize_entwined,
    entwine_mana_needed,
    resolve_burn_damage,
    has_bestow,
    has_overload,
    normalize_overloaded,
    overload_hits_each_creature,
    overload_mana_needed,
    bestow_host_error,
    bestow_mana_needed,
    normalize_bestow,
    escape_cost,
    escape_exiles_required,
    escape_mana_needed,
    escape_payment_error,
    exile_for_escape_cost,
    flashback_cost,
    flashback_mana_needed,
    has_convoke,
    has_escape,
    has_delve,
    has_flashback,
    has_improvise,
    has_kicker,
    is_multikicker,
    kicker_mana_per_time,
    normalize_convoke_creature_ids,
    normalize_delve_graveyard_indices,
    normalize_improvise_artifact_ids,
    normalize_kicker_times,
    resolve_convoke_for_cast,
    resolve_delve_for_cast,
    resolve_improvise_for_cast,
    spell_damage,
    storm_copy_count,
    supports_storm_copies,
    has_miracle,
    has_replicate,
    miracle_cost,
    miracle_mana_needed,
    normalize_miracle_cast,
    normalize_replicate_times,
    replicate_extra_mana,
    replicate_mana_per_time,
    supports_replicate_copies,
)
from engine.abilities.keywords.casting.cascade import (
    has_cascade,
    reveal_cascade_hit,
    return_cascade_bottom,
)
from engine.abilities.activated import ActivationSpeed
from engine.abilities.keywords import (
    KEYWORD_ENTRIES,
    SCRYFALL_KEYWORD_COUNT,
    detect_keywords,
    has_registered_keyword,
    registry_summary,
)
from engine.core.game_object import (
    CardObject,
    SpellOnStack,
    Target,
    ZoneCard,
    spell_returns_to_hand_on_resolve,
)
from engine.core.mana import ManaCost
from engine.core.zones import Zone
from engine.rules.combat import legal_blocker, resolve_combat_damage
from tests.conftest import (
    fresh_game,
    make_card,
    make_creature,
    make_instant,
    make_land,
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
    game = fresh_game()
    protected = place_on_battlefield(
        make_creature('Slippery', oracle='Hexproof'),
        0,
        game.zones,
    )
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
    creature_source = keywords.protection_source_from_flags(source_is_creature=True)
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
    card = make_instant(
        'Charm',
        cmc=0,
        oracle=(
            'Choose one —\n'
            '• Charm deals 2 damage to any target.\n'
            '• Target player draws a card.\n'
            'Entwine {2}'
        ),
    )
    assert has_entwine(card)
    cost = entwine_cost(card)
    assert cost is not None
    assert cost.mana_value == 2
    assert entwine_mana_needed(card) == 2
    assert normalize_entwined(card, True)
    assert not normalize_entwined(card, False)
    assert cast_mana_with_entwine(card, 0, 0, True) == (2, 0)


def test_entwined_charm_deals_damage_and_draws():
    """Entwined modal charms apply damage plus the draw mode (MVP)."""
    card = make_instant(
        'Charm',
        cmc=0,
        oracle=(
            'Choose one —\n'
            '• Charm deals 2 damage to any target.\n'
            '• Target player draws a card.\n'
            'Entwine {0}'
        ),
    )
    assert resolve_burn_damage(card, False, 0) == 2
    assert resolve_burn_damage(card, True, 0) == 2
    assert entwined_extra_draw(card, False) == 0
    assert entwined_extra_draw(card, True) == 1


def test_has_aftermath_and_main_phase_timing():
    """Aftermath is detected and only castable in a main phase with an empty stack."""
    card = make_instant(
        'Start',
        cmc=2,
        oracle='Aftermath\nCreate a 2/2 black Zombie creature token.',
    )
    assert has_aftermath(card)
    assert aftermath_mana_needed(card) == (2, 0)
    assert can_cast_aftermath(card, 'main1', stack_is_empty=True)
    assert not can_cast_aftermath(card, 'attack', stack_is_empty=True)
    assert not can_cast_aftermath(card, 'main1', stack_is_empty=False)


def test_has_jump_start_parses_alternate_cost():
    """Jump-start cost is parsed from oracle text."""
    card = make_instant(
        'Bolt',
        oracle='Jump-start {1}{R}\nBolt deals 2 damage to any target.',
    )
    assert has_jump_start(card)
    cost = jump_start_cost(card)
    assert cost is not None
    assert cost.mana_value == 2
    assert jump_start_mana_needed(card) == 2


def test_has_retrace_and_normal_mana_cost():
    """Retrace uses the card's printed mana cost, not a separate alt cost."""
    card = make_instant(
        'Loam',
        cmc=2,
        mana_cost='{1}{G}',
        oracle='Draw a card.\nRetrace',
    )
    assert has_retrace(card)
    assert retrace_mana_needed(card) == 2


def test_discard_land_for_retrace_requires_land():
    """Retrace rejects non-land discards."""
    game = fresh_game()
    game.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Bolt')),
        CardObject(controller_idx=0, owner_idx=0, card_info=make_land('Island')),
    ]
    assert retrace_land_discard_error(game.zones, 0, None) == "Retrace requires discarding a land card"
    assert retrace_land_discard_error(game.zones, 0, 0) == "Retrace requires discarding a land card"
    assert retrace_land_discard_error(game.zones, 0, 1) is None
    discarded = discard_land_for_retrace(game.zones, 0, 1)
    assert discarded.card_info is not None
    assert discarded.card_info.is_land
    assert len(game.zones.player_zones[0].hand) == 1
    assert len(game.zones.player_zones[0].graveyard) == 1


def test_can_cast_via_retrace_follows_spell_timing():
    """Instant-speed retrace works in combat; sorcery retrace needs a main phase."""
    instant = make_instant('Charm', oracle='Retrace\nDeal 1 damage.')
    sorcery = make_card(
        name='Ritual',
        type_line='Sorcery',
        cmc=2.0,
        oracle='Draw a card.\nRetrace',
    )
    assert can_cast_via_retrace(instant, 'attack', stack_is_empty=False)
    assert not can_cast_via_retrace(sorcery, 'attack', stack_is_empty=False)
    assert can_cast_via_retrace(sorcery, 'main1', stack_is_empty=True)


def test_discard_for_jump_start_moves_card_to_graveyard():
    """Jump-start discard removes a card from hand and puts it in the graveyard."""
    game = fresh_game()
    to_discard = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Fodder'))
    game.zones.player_zones[0].hand.append(to_discard)
    assert jump_start_discard_error(game.zones, 0, 0) is None
    discarded = discard_for_jump_start(game.zones, 0, 0)
    assert discarded.card_info is not None
    assert discarded.card_info.name == 'Fodder'
    assert len(game.zones.player_zones[0].hand) == 0
    assert to_discard in game.zones.player_zones[0].graveyard


def test_can_cast_via_jump_start_allows_instant_timing():
    """Jump-start may be cast during combat steps like an instant."""
    card = make_instant('Bolt', oracle='Jump-start {0}\nDeal 2 damage.')
    assert can_cast_via_jump_start(card, 'attack', stack_is_empty=False)
    assert not can_cast_via_jump_start(card, 'upkeep', stack_is_empty=True)


def test_can_cast_via_escape_allows_instant_timing():
    """Escape may be cast during combat steps like an instant."""
    card = make_instant('Scream', oracle='Escape—{0}\nExile two other cards.')
    assert can_cast_via_escape(card, 'attack', stack_is_empty=False)
    assert not can_cast_via_escape(card, 'upkeep', stack_is_empty=True)


def test_buyback_cost_and_extra_mana():
    """Buyback cost parses and adds to announce mana when paid."""
    card = make_instant(
        'Echo',
        oracle='Deal 2 damage to any target. Buyback {3}',
    )
    assert has_buyback(card)
    assert buyback_mana_needed(card) == 3
    assert buyback_cost(card) is not None
    assert normalize_buyback(card, True)
    assert not normalize_buyback(card, False)
    assert buyback_extra_mana(card, True) == 3
    assert buyback_extra_mana(card, False) == 0


def test_spell_returns_to_hand_on_resolve_only_with_buyback():
    """Buyback flag routes resolved spells to hand; copies and unpaid casts do not."""
    card = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_instant('Echo', oracle='Buyback {1}\nDeal 1 damage.'),
    )
    buyback_spell = SpellOnStack(controller_idx=0, owner_idx=0, source=card, paid_buyback=True)
    assert spell_returns_to_hand_on_resolve(buyback_spell)
    unpaid = SpellOnStack(controller_idx=0, owner_idx=0, source=card, paid_buyback=False)
    assert not spell_returns_to_hand_on_resolve(unpaid)
    copy = SpellOnStack(
        controller_idx=0,
        owner_idx=0,
        source=card,
        paid_buyback=True,
        is_storm_copy=True,
    )
    assert not spell_returns_to_hand_on_resolve(copy)


def test_kicker_cost_and_kicked_damage():
    """Kicker cost parses and kicked burn uses the replacement damage."""
    card = make_instant(
        'Burst',
        oracle=(
            'Deals 2 damage to any target. Kicker {4}. '
            'If this spell was kicked, it deals 4 damage instead.'
        ),
    )
    assert has_kicker(card)
    assert not is_multikicker(card)
    assert kicker_mana_per_time(card) == 4
    assert spell_damage(card, 0) == 2
    assert spell_damage(card, 1) == 4
    assert cast_mana_needed(card, 1)[0] == int(card.cmc) + 4


def test_reveal_cascade_hit_finds_lower_mana_nonland():
    """Cascade exiles from the top until a nonland with lower mana value."""
    land = make_land()
    hit_info = make_instant('Hit', cmc=2, oracle='Deal 1 damage.')
    miss_info = make_instant('Big', cmc=4, oracle='Deal 4 damage.')
    library: list[ZoneCard] = [
        CardObject(controller_idx=0, owner_idx=0, card_info=land),
        CardObject(controller_idx=0, owner_idx=0, card_info=hit_info),
        CardObject(controller_idx=0, owner_idx=0, card_info=miss_info),
    ]
    reveal = reveal_cascade_hit(library, max_mana_value=4)
    return_cascade_bottom(library, reveal.bottom_cards)
    assert reveal.hit is not None
    assert reveal.hit.card_info is not None
    assert reveal.hit.card_info.name == 'Hit'
    assert len(library) == 2
    names = {
        c.card_info.name
        for c in library
        if isinstance(c, CardObject) and c.card_info is not None
    }
    assert names == {'Plains', 'Big'}


def test_has_cascade_detects_keyword():
    """Cascade is detected on oracle text."""
    card = make_instant('Boarder', oracle='Cascade')
    assert has_cascade(card)


def test_has_convoke_detects_keyword():
    """Convoke is detected on oracle text."""
    card = make_instant('Mob', oracle='Convoke\nDeal 4 damage.')
    assert has_convoke(card)


def test_resolve_convoke_taps_creatures_and_reduces_mana():
    """Each convoked creature taps and reduces generic mana by one."""
    game = fresh_game()
    spell = make_instant('Mob', cmc=4, oracle='Convoke\nDeal 4 damage.')
    creature_a = place_on_battlefield(make_creature('Soldier'), 0, game.zones)
    creature_b = place_on_battlefield(make_creature('Knight'), 0, game.zones)
    ids = [creature_a.obj_id, creature_b.obj_id]
    assert normalize_convoke_creature_ids(spell, ids) == ids
    mana_left, tapped, err = resolve_convoke_for_cast(spell, 4, ids, game.zones, 0)
    assert err is None
    assert mana_left == 2
    assert tapped == ids
    assert creature_a.tapped and creature_b.tapped


def test_has_delve_and_exiles_graveyard_cards():
    """Delve exiles graveyard cards and reduces generic mana by one each."""
    game = fresh_game()
    spell = make_instant('Dig', cmc=3, oracle='Delve\nDraw a card.')
    filler = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Filler'))
    game.zones.player_zones[0].graveyard.extend([filler, filler])
    assert has_delve(spell)
    assert normalize_delve_graveyard_indices(spell, [0, 1]) == [0, 1]
    mana_left, exiled, err = resolve_delve_for_cast(spell, 3, [0, 1], game.zones, 0)
    assert err is None
    assert mana_left == 1
    assert exiled == 2
    assert len(game.zones.player_zones[0].graveyard) == 0
    assert len(game.zones.player_zones[0].exile) == 2


def test_resolve_improvise_taps_artifacts_and_reduces_mana():
    """Each improvised artifact taps and reduces generic mana by one."""
    game = fresh_game()
    spell = make_instant('Scheme', cmc=3, oracle='Improvise\nDraw a card.')
    relic = place_on_battlefield(
        make_card('Relic', type_line='Artifact'),
        0,
        game.zones,
    )
    assert has_improvise(spell)
    ids = [relic.obj_id]
    assert normalize_improvise_artifact_ids(spell, ids) == ids
    mana_left, tapped, err = resolve_improvise_for_cast(spell, 3, ids, game.zones, 0)
    assert err is None
    assert mana_left == 2
    assert tapped == ids
    assert relic.tapped


def test_storm_copy_count_is_other_spells_this_turn():
    """Storm copies equal other spells cast before this one."""
    assert storm_copy_count(1) == 0
    assert storm_copy_count(2) == 1
    assert storm_copy_count(5) == 4


def test_supports_storm_copies_excludes_creatures():
    """Creature storm is not modeled yet; instants with storm are."""
    instant = make_instant('Grapeshot', oracle='Storm\nDeals 1 damage.')
    creature = make_creature('Aven', oracle='Storm')
    assert supports_storm_copies(instant)
    assert not supports_storm_copies(creature)


def test_multikicker_normalizes_times():
    """Multikicker allows paying more than once; regular kicker does not."""
    multi = make_instant('Strength', oracle='Multikicker {1}\nDraw a card.')
    single = make_instant('Bolt', oracle='Kicker {2}\nDeals 3 damage.')
    assert is_multikicker(multi)
    assert normalize_kicker_times(multi, 3) == 3
    assert normalize_kicker_times(single, 3) == 1
    assert normalize_kicker_times(single, 0) == 0


def test_flashback_fizzle_exiles_source_card():
    """Fizzled flashback spells exile instead of going to the graveyard."""
    game = fresh_game()
    card_info = make_instant('Charm', oracle='Flashback {0}\nDeal 1 damage.')
    card = CardObject(controller_idx=0, owner_idx=0, card_info=card_info)
    spell = SpellOnStack(
        controller_idx=1,
        owner_idx=0,
        source=card,
        cast_via_flashback=True,
        targets=[Target(obj_id=99999)],
    )
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones)
    assert result.fizzled
    assert card in game.zones.player_zones[0].exile
    assert card not in game.zones.player_zones[0].graveyard


def test_aftermath_fizzle_exiles_source_card():
    """Fizzled aftermath spells exile instead of returning to the graveyard."""
    game = fresh_game()
    card_info = make_instant('Start', oracle='Aftermath\nDeal 1 damage.')
    card = CardObject(controller_idx=0, owner_idx=0, card_info=card_info)
    spell = SpellOnStack(
        controller_idx=1,
        owner_idx=0,
        source=card,
        cast_via_aftermath=True,
        targets=[Target(obj_id=99999)],
    )
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones)
    assert result.fizzled
    assert card in game.zones.player_zones[0].exile
    assert card not in game.zones.player_zones[0].graveyard


def test_jump_start_fizzle_exiles_source_card():
    """Fizzled jump-start spells exile instead of returning to the graveyard."""
    game = fresh_game()
    card_info = make_instant('Bolt', oracle='Jump-start {0}\nDeal 2 damage.')
    card = CardObject(controller_idx=0, owner_idx=0, card_info=card_info)
    spell = SpellOnStack(
        controller_idx=1,
        owner_idx=0,
        source=card,
        cast_via_jump_start=True,
        targets=[Target(obj_id=99999)],
    )
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones)
    assert result.fizzled
    assert card in game.zones.player_zones[0].exile
    assert card not in game.zones.player_zones[0].graveyard


def test_escape_fizzle_exiles_source_card():
    """Fizzled escape spells exile instead of returning to the graveyard."""
    game = fresh_game()
    card_info = make_instant('Scream', oracle='Escape—{0}\nExile two other cards.')
    card = CardObject(controller_idx=0, owner_idx=0, card_info=card_info)
    spell = SpellOnStack(
        controller_idx=1,
        owner_idx=0,
        source=card,
        cast_via_escape=True,
        targets=[Target(obj_id=99999)],
    )
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones)
    assert result.fizzled
    assert card in game.zones.player_zones[0].exile
    assert card not in game.zones.player_zones[0].graveyard


def test_hexproof_spell_fizzles_on_stack():
    """Targeting a hexproof permanent fizzles when the opponent controls the spell."""
    game = fresh_game()
    protected = place_on_battlefield(
        make_creature('Slippery', oracle='Hexproof'),
        0,
        game.zones,
    )
    spell = SpellOnStack(
        controller_idx=1,
        owner_idx=1,
        targets=[Target(obj_id=protected.obj_id)],
    )
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones)
    assert result.fizzled


def test_infect_combat_damage_adds_poison():
    """Infect damage to a player gives poison counters."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Vector', 1, 1, oracle='Infect'),
        1,
        game.zones,
        sick=False,
    )
    result = resolve_combat_damage(
        game,
        attacking_player_idx=1,
        defending_player_idx=0,
        attacker_ids=[str(attacker.obj_id)],
        blocker_assignments={},
    )
    assert result.infect_damage_to_player == 1
    assert game.players[0].poison == 1


def test_persist_returns_creature_without_minus_counter():
    """Persist returns a creature to the battlefield with -1/-1 when it had none."""
    game = fresh_game()
    creature = place_on_battlefield(
        make_creature('Puppet', 2, 2, oracle='Persist'),
        0,
        game.zones,
    )
    creature.damage_marked = 2
    game.zones.leave_battlefield(creature, Zone.GRAVEYARD, 'lethal', game)
    assert creature in game.zones.battlefield
    assert creature.counters.get('-1/-1') == 1


def test_undying_returns_creature_without_plus_counter():
    """Undying returns a creature with +1/+1 when it had none."""
    game = fresh_game()
    creature = place_on_battlefield(
        make_creature('Hyena', 2, 2, oracle='Undying'),
        0,
        game.zones,
    )
    game.zones.leave_battlefield(creature, Zone.GRAVEYARD, 'destroy', game)
    assert creature in game.zones.battlefield
    assert creature.counters.get('+1/+1') == 1


def test_shadow_requires_shadow_blocker():
    """Shadow attackers require shadow blockers."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Shade', 2, 2, oracle='Shadow'),
        1,
        game.zones,
    )
    ground = place_on_battlefield(make_creature('Bear', 2, 2), 0, game.zones)
    shadow = place_on_battlefield(
        make_creature('Ninja', 1, 1, oracle='Shadow'),
        0,
        game.zones,
    )
    assert not legal_blocker(ground, attacker, game)
    assert legal_blocker(shadow, attacker, game)


def test_islandwalk_unblockable_when_defender_has_island():
    """Islandwalk makes an attacker unblockable when the defender controls an island."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Pirate', 2, 2, oracle='Islandwalk'),
        1,
        game.zones,
        sick=False,
    )
    blocker = place_on_battlefield(make_creature('Soldier', 2, 2), 0, game.zones)
    place_on_battlefield(make_land('Island'), 0, game.zones, sick=False)
    result = resolve_combat_damage(
        game,
        attacking_player_idx=1,
        defending_player_idx=0,
        attacker_ids=[str(attacker.obj_id)],
        blocker_assignments={str(blocker.obj_id): str(attacker.obj_id)},
    )
    assert result.damage_to_player == 2


def test_mana_ability_resolves_without_stack():
    """Mana abilities add mana immediately without using the stack."""
    game = fresh_game()
    land = place_on_battlefield(
        make_land('Plains', 'W'),
        0,
        game.zones,
        sick=False,
    )
    spec = activated.ActivatedAbilitySpec(
        cost_text='{T}',
        effect_text='Add {W}.',
        mana_ability=True,
    )
    result = activated.activate_mana_ability(game, land, spec)
    assert 'added' in result.lower()
    assert land.tapped
    assert game.players[0].mana_pool.can_pay(ManaCost.parse('{W}'))


def test_equip_attaches_to_creature():
    """Equip activated ability attaches equipment to a creature host."""
    game = fresh_game()
    host = place_on_battlefield(make_creature('Soldier', 2, 2), 0, game.zones)
    sword = place_on_battlefield(
        make_card('Sword', type_line='Artifact — Equipment', oracle='Equip {2}'),
        0,
        game.zones,
    )
    game.players[0].mana_pool.add_color('C', 2)
    spec = activated.ActivatedAbilitySpec(
        cost_text='Equip {2}',
        effect_text='Attach to target creature.',
        equip=True,
    )
    result = activated.activate_equip(game, sword, host, spec)
    assert result.ok
    assert sword.attached_to == host.obj_id


def test_equip_requires_sorcery_speed():
    """Equip cannot be activated while the stack is not empty."""
    game = fresh_game()
    sword = place_on_battlefield(
        make_card('Sword', type_line='Artifact — Equipment', oracle='Equip {1}'),
        0,
        game.zones,
    )
    spec = activated.ActivatedAbilitySpec(cost_text='Equip {1}', effect_text='', equip=True)
    game.stack.push(SpellOnStack(controller_idx=0, owner_idx=0))
    assert not activated.can_activate(
        sword,
        spec,
        game,
        0,
        ActivationSpeed.SORCERY,
    )


def test_has_registered_keyword_unknown_falls_back_to_substring():
    """Unknown strings still match via substring fallback."""
    assert has_registered_keyword('Custom card with banding', 'banding')
