"""Unit tests for Scryfall keyword registry and keyword hooks (Phase E, 2026)."""

from __future__ import annotations

import pytest

from engine.abilities import activated, keywords
from engine.abilities.activated import ActivationSpeed
from engine.abilities.keywords import (
    KEYWORD_ENTRIES,
    SCRYFALL_KEYWORD_COUNT,
    detect_keywords,
    has_registered_keyword,
    registry_summary,
)
from engine.core.game_object import SpellOnStack, Target
from engine.core.mana import ManaCost
from engine.core.zones import Zone
from engine.rules.combat import legal_blocker, resolve_combat_damage
from tests.conftest import fresh_game, make_card, make_creature, make_land, place_on_battlefield


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
    assert not keywords.can_target_permanent(protected, 1, source_is_creature=True)
    assert keywords.can_target_permanent(protected, 1, source_is_creature=False)


def test_protection_from_red_blocks_red_sources():
    """Protection from red blocks red-colored sources."""
    game = fresh_game()
    protected = place_on_battlefield(
        make_creature('Knight', oracle='Protection from red'),
        0,
        game.zones,
    )
    assert not keywords.can_target_permanent(protected, 1, source_colors=frozenset({'R'}))


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
