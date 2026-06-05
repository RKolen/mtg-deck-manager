"""Unit tests for keyword hooks: entwine through equip (Phase E, 2026)."""

from __future__ import annotations

from engine.abilities import activated
from engine.abilities.keywords.casting.delayed_exile_cast import _CastTiming
from engine.abilities.keywords.casting import (
    aftermath_mana_needed,
    buyback_cost,
    buyback_extra_mana,
    buyback_mana_needed,
    can_cast_aftermath,
    can_cast_foretold,
    can_cast_via_escape,
    can_cast_via_jump_start,
    can_cast_via_retrace,
    cast_mana_needed,
    discard_for_jump_start,
    discard_land_for_retrace,
    entwined_extra_draw,
    exile_for_foretell,
    exile_for_plot,
    FORETELL_EXILE_MODE,
    foretell_setup_error,
    has_aftermath,
    has_buyback,
    has_cascade,
    has_convoke,
    has_jump_start,
    has_kicker,
    has_mutate,
    has_retrace,
    has_spree,
    is_multikicker,
    is_plottable_sorcery,
    jump_start_cost,
    jump_start_discard_error,
    jump_start_mana_needed,
    kicker_mana_per_time,
    mutate_host_error,
    mutate_mana_needed,
    normalize_buyback,
    normalize_kicker_times,
    normalize_spree_modes,
    PLOT_EXILE_MODE,
    resolve_burn_damage,
    retrace_land_discard_error,
    retrace_mana_needed,
    spell_damage,
    spree_extra_mana,
    spree_modes,
    spree_selection_error,
    supports_storm_copies,
)
from engine.abilities.keywords.casting.cascade import (
    reveal_cascade_hit,
    return_cascade_bottom,
)
from engine.abilities.activated import ActivationSpeed
from engine.abilities.keywords import (
    has_registered_keyword,
)
from engine.core.game_object import (
    CardObject,
    SpellAlternateCast,
    SpellCastPayment,
    SpellOnStack,
    SpellStackCopyFlags,
    _CostMods,
    _GraveyardAlts,
    _SpellCasting,
    _SpellCopy,
    Target,
    ZoneCard,
    spell_returns_to_hand_on_resolve,
)
from engine.core.mana import ManaCost
from engine.core.zones import Zone
from engine.rules.combat import legal_blocker
from tests.conftest import resolve_single_attacker
from tests.conftest import (
    _CardStats,
    fresh_game,
    hexproof_game_setup,
    make_card,
    make_creature,
    make_entwine_charm,
    make_instant,
    make_land,
    place_on_battlefield,
)


def test_entwined_charm_deals_damage_and_draws():
    """Entwined modal charms apply damage plus the draw mode (MVP)."""
    card = make_entwine_charm('{0}')
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


def test_spree_modes_parse_and_extra_mana():
    """Spree bullets parse costs and add mana for each chosen mode."""
    card = make_instant(
        'Score',
        oracle=(
            'Spree\n'
            '• {2} — Draw a card.\n'
            '• {3} — Score deals 2 damage to any target.'
        ),
    )
    assert has_spree(card)
    modes = spree_modes(card)
    assert len(modes) == 2
    assert modes[0].mana_value == 2
    assert modes[1].mana_value == 3
    chosen = normalize_spree_modes(card, [1, 0, 99])
    assert chosen == (0, 1)
    assert spree_extra_mana(card, chosen) == 5
    assert spree_selection_error(card, []) == "Spree requires choosing at least one mode"


def test_has_mutate_and_host_validation():
    """Mutate parses cost and rejects Human hosts when required."""
    card = make_creature(
        'Snapdax',
        oracle='Mutate {2}{U}{B}{R}\nMutate onto a non-Human creature.',
    )
    assert has_mutate(card)
    assert mutate_mana_needed(card)[0] == 5
    game = fresh_game()
    human = place_on_battlefield(
        make_card(name='Soldier', type_line='Creature — Human Soldier'),
        0,
        game.zones,
    )
    beast = place_on_battlefield(make_creature('Beast'), 0, game.zones)
    assert mutate_host_error(game.zones, 0, card, str(human.obj_id)) is not None
    assert mutate_host_error(game.zones, 0, card, str(beast.obj_id)) is None


def test_foretell_exile_and_cast_timing():
    """Foretell setup exiles a card; foretold instants cast at instant speed."""
    card = make_instant('Glimpse', oracle='Draw a card.\nForetell {1}{U}')
    game = fresh_game()
    game.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=card),
    ]
    assert foretell_setup_error(
        game.zones, 0, 0, card, _CastTiming(phase='main1', stack_is_empty=True)
    ) is None
    exiled = exile_for_foretell(game.zones, 0, 0)
    assert exiled.exiled_cast_mode == FORETELL_EXILE_MODE
    assert can_cast_foretold(card, _CastTiming(phase='attack', stack_is_empty=False))


def test_plot_only_sorceries():
    """Plot applies to sorceries and exiles them for a free later cast."""
    sorcery = make_card(name='Heist', type_line='Sorcery', oracle='Draw two cards.\nPlot')
    instant = make_instant('Bolt', oracle='Plot')
    assert is_plottable_sorcery(sorcery)
    assert not is_plottable_sorcery(instant)
    game = fresh_game()
    game.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=sorcery),
    ]
    plotted = exile_for_plot(game.zones, 0, 0)
    assert plotted.exiled_cast_mode == PLOT_EXILE_MODE


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
    retrace_err = "Retrace requires discarding a land card"
    assert retrace_land_discard_error(game.zones, 0, None) == retrace_err
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
        stats=_CardStats(cmc=2.0, pt="0/0"),
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
    buyback_spell = SpellOnStack(
        controller_idx=0,
        owner_idx=0,
        source=card,
        casting=_SpellCasting(payment=SpellCastPayment(costs=_CostMods(paid_buyback=True)),),
    )
    assert spell_returns_to_hand_on_resolve(buyback_spell)
    unpaid = SpellOnStack(
        controller_idx=0,
        owner_idx=0,
        source=card,
        casting=_SpellCasting(payment=SpellCastPayment(costs=_CostMods(paid_buyback=False)),),
    )
    assert not spell_returns_to_hand_on_resolve(unpaid)
    copy = SpellOnStack(
        controller_idx=0,
        owner_idx=0,
        source=card,
        casting=_SpellCasting(
            payment=SpellCastPayment(costs=_CostMods(paid_buyback=True)),
            copies=SpellStackCopyFlags(copy_source=_SpellCopy(storm=True)),
        ),
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
        casting=_SpellCasting(alternate=SpellAlternateCast(
            graveyard=_GraveyardAlts(flashback=True)
        ),),
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
        casting=_SpellCasting(alternate=SpellAlternateCast(
            graveyard=_GraveyardAlts(aftermath=True)
        ),),
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
        casting=_SpellCasting(alternate=SpellAlternateCast(
            graveyard=_GraveyardAlts(jump_start=True)
        ),),
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
        casting=_SpellCasting(alternate=SpellAlternateCast(
            graveyard=_GraveyardAlts(escape=True)
        ),),
        targets=[Target(obj_id=99999)],
    )
    game.stack.push(spell)
    result = game.stack.resolve_top(game.zones)
    assert result.fizzled
    assert card in game.zones.player_zones[0].exile
    assert card not in game.zones.player_zones[0].graveyard


def test_hexproof_spell_fizzles_on_stack():
    """Targeting a hexproof permanent fizzles when the opponent controls the spell."""
    game, protected = hexproof_game_setup()
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
    result = resolve_single_attacker(game, attacker)
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
    result = resolve_single_attacker(
        game,
        attacker,
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
