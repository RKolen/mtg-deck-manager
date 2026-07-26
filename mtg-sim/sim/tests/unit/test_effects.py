"""Unit tests for engine/cards/effects.py and script_loader.py (Phase G)."""

from engine.cards.effects import (
    CardEffectContext,
    _CardEffectTargets,
    ConditionalEffect,
    CreateToken,
    DealDamage,
    DealDamageToPlayer,
    DeliriumDealDamage,
    DestroyPermanent,
    DiscardCards,
    DrainLife,
    DrawCards,
    EffectList,
    ExilePermanent,
    FightCreatures,
    GainLife,
    LoseLife,
    LoseLifeEachOpponent,
    Mill,
    Modal,
    NoEffect,
    PumpUntilEOT,
    Scry,
    Surveil,
    SwitchPowerToughnessUntilEOT,
    TreasureHunt,
)
from engine.cards.effect_serde import effect_from_dict, effect_to_dict
from engine.cards.oracle_parse import TokenBlueprint
from engine.cards.script_loader import has_script, resolve_scripted_spell, scripted_card_names
from engine.core.game_object import CardObject, effective_power, effective_toughness
from engine.rules.modifiers import clear_until_end_of_turn_modifiers
from tests.conftest import (
    add_to_library,
    fresh_game,
    make_card,
    make_creature,
    make_instant,
    make_land,
    place_on_battlefield,
)


def _card(name: str, oracle: str = '') -> CardObject:
    return CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_card(name=name, type_line='Sorcery', oracle=oracle),
    )


def _ctx(
    game,
    *,
    target_player_idx: int | None = None,
    target_creature_uid: str | None = None,
    selected_mode: int | None = None,
) -> CardEffectContext:
    return CardEffectContext(
        game=game,
        controller_idx=0,
        source=_card('Test'),
        targets=_CardEffectTargets(
            player_idx=target_player_idx,
            creature_uid=target_creature_uid,
        ),
        selected_mode=selected_mode,
    )


def test_mill_moves_library_cards_to_graveyard():
    """Mill sends the top cards of the opponent's library to the graveyard."""
    game = fresh_game()
    for idx in range(3):
        add_to_library(make_instant(f'C{idx}'), 1, game.zones)
    detail = Mill(count=2, target='opponent').apply(_ctx(game))
    assert 'milled 2' in detail
    assert len(game.zones.player_zones[1].graveyard) == 2


def test_mill_each_player():
    """Mill with target each hits both libraries."""
    game = fresh_game()
    add_to_library(make_instant('A'), 0, game.zones)
    add_to_library(make_instant('B'), 1, game.zones)
    detail = Mill(count=1, target='each').apply(_ctx(game))
    assert 'P1 milled 1' in detail
    assert 'P2 milled 1' in detail


def test_draw_cards_uses_zones_draw():
    """DrawCards moves cards from library to hand."""
    game = fresh_game()
    add_to_library(make_instant('Drawn'), 0, game.zones)
    detail = DrawCards(count=1).apply(_ctx(game))
    assert detail == 'drew 1 card(s)'
    assert len(game.zones.player_zones[0].hand) == 1


def test_gain_and_lose_life():
    """GainLife and LoseLife adjust the controller's life total."""
    game = fresh_game()
    assert GainLife(amount=3).apply(_ctx(game)) == 'gained 3 life'
    assert game.players[0].life == 23
    assert LoseLife(amount=2).apply(_ctx(game)) == 'lost 2 life'
    assert game.players[0].life == 21


def test_deal_damage_to_player():
    """DealDamageToPlayer reduces the opponent's life."""
    game = fresh_game()
    detail = DealDamageToPlayer(amount=4, target='opponent').apply(_ctx(game))
    assert detail == 'dealt 4 to P2'
    assert game.players[1].life == 16


def test_scry_puts_cards_on_bottom():
    """Scry reorders the top of the library."""
    game = fresh_game()
    add_to_library(make_instant('Second'), 0, game.zones)
    add_to_library(make_instant('Top'), 0, game.zones)
    detail = Scry(count=2, bottom_indices=(0,)).apply(_ctx(game))
    assert 'scry 2' in detail
    lib = game.zones.player_zones[0].library
    top = lib[0]
    assert isinstance(top, CardObject)
    assert top.card_info is not None
    assert top.card_info.name == 'Second'


def test_effect_list_applies_in_order():
    """EffectList runs child effects sequentially."""
    game = fresh_game()
    add_to_library(make_instant('Top'), 0, game.zones)
    detail = EffectList((
        GainLife(amount=2),
        DrawCards(count=1),
    )).apply(_ctx(game))
    assert 'gained 2 life' in detail
    assert 'drew 1 card(s)' in detail
    assert game.players[0].life == 22


def test_conditional_effect_branches():
    """ConditionalEffect picks when_true or when_false."""
    game = fresh_game()
    true_effect = ConditionalEffect(
        condition=lambda ctx: ctx.controller_idx == 0,
        when_true=GainLife(amount=1),
        when_false=LoseLife(amount=1),
    )
    assert 'gained 1 life' in true_effect.apply(_ctx(game))
    false_effect = ConditionalEffect(
        condition=lambda ctx: ctx.controller_idx == 1,
        when_true=GainLife(amount=5),
        when_false=GainLife(amount=1),
    )
    assert 'gained 1 life' in false_effect.apply(_ctx(game))


def test_script_loader_returns_none_for_unscripted_card():
    """Unscripted cards return None so regex handlers can run."""
    game = fresh_game()
    source = _card('Random Spell')
    ctx = CardEffectContext(game=game, controller_idx=0, source=source)
    assert resolve_scripted_spell(ctx) is None


def test_deal_damage_to_creature_marks_damage():
    """DealDamage applies marked damage when a creature is targeted."""
    game = fresh_game()
    creature = place_on_battlefield(make_creature('Target', 2, 2), 1, game.zones)
    detail = DealDamage(amount=3).apply(
        _ctx(game, target_creature_uid=str(creature.obj_id)),
    )
    assert 'dealt 3 to Target' in detail
    assert creature.damage_marked == 3


def test_deal_damage_to_player_when_no_creature_target():
    """DealDamage hits the opponent when no creature target is set."""
    game = fresh_game()
    detail = DealDamage(amount=3).apply(_ctx(game))
    assert detail == 'dealt 3 to P2'
    assert game.players[1].life == 17


def test_destroy_permanent_leaves_battlefield():
    """DestroyPermanent removes the targeted creature."""
    game = fresh_game()
    doomed = place_on_battlefield(make_creature('Doomed', 2, 2), 1, game.zones)
    detail = DestroyPermanent().apply(
        _ctx(game, target_creature_uid=str(doomed.obj_id)),
    )
    assert 'destroyed Doomed' in detail
    assert doomed not in game.zones.battlefield


def test_exile_permanent_sends_card_to_exile():
    """ExilePermanent moves the creature's card to exile."""
    game = fresh_game()
    victim = place_on_battlefield(make_creature('Victim', 2, 2), 1, game.zones)
    detail = ExilePermanent().apply(
        _ctx(game, target_creature_uid=str(victim.obj_id)),
    )
    assert 'exiled Victim' in detail
    assert victim not in game.zones.battlefield
    assert len(game.zones.player_zones[1].exile) == 1


def test_modal_resolves_selected_mode_only():
    """Modal applies only the chosen mode effect."""
    game = fresh_game()
    modal = Modal(modes=(
        GainLife(amount=5),
        LoseLife(amount=2),
    ))
    assert 'gained 5 life' in modal.apply(_ctx(game, selected_mode=0))
    assert game.players[0].life == 25
    game.players[0].life = 20
    assert 'lost 2 life' in modal.apply(_ctx(game, selected_mode=1))
    assert game.players[0].life == 18


def test_lightning_bolt_script_registered():
    """Lightning Bolt is in the card script registry."""
    assert 'Lightning Bolt' in scripted_card_names()


def test_script_loader_lightning_bolt_deals_three():
    """Lightning Bolt script deals three damage to the opponent."""
    game = fresh_game()
    source = _card('Lightning Bolt', oracle='Lightning Bolt deals 3 damage to any target.')
    ctx = CardEffectContext(game=game, controller_idx=0, source=source)
    assert source.card_info is not None
    assert has_script(source.card_info) is True
    detail = resolve_scripted_spell(ctx)
    assert detail == 'dealt 3 to P2'
    assert game.players[1].life == 17


def test_treasure_hunt_puts_revealed_cards_in_hand():
    """TreasureHunt reveals until a nonland and puts cards in hand."""
    game = fresh_game()
    add_to_library(make_instant('Shock'), 0, game.zones)
    add_to_library(make_land('Forest'), 0, game.zones)
    detail = TreasureHunt().apply(_ctx(game))
    assert '2 card' in detail
    assert len(game.zones.player_zones[0].hand) == 2


def test_switch_power_toughness_until_eot():
    """SwitchPowerToughnessUntilEOT swaps layered P/T until cleanup."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature('Bear', 2, 5), 0, game.zones)
    detail = SwitchPowerToughnessUntilEOT().apply(
        _ctx(game, target_creature_uid=str(bear.obj_id)),
    )
    assert 'switched Bear' in detail
    assert effective_power(bear, game) == 5
    assert effective_toughness(bear, game) == 2
    clear_until_end_of_turn_modifiers(game)
    assert effective_power(bear, game) == 2
    assert effective_toughness(bear, game) == 5


def test_effect_serde_roundtrip_switch_pt():
    """SwitchPowerToughnessUntilEOT survives JSON serialization."""
    effect = SwitchPowerToughnessUntilEOT()
    restored = effect_from_dict(effect_to_dict(effect))
    assert restored == effect


def test_collective_brutality_drain_mode():
    """Modal drain mode deals life loss and gain."""
    game = fresh_game()
    modal = Modal(modes=(
        NoEffect(),
        PumpUntilEOT(power=-2, toughness=-2),
        DrainLife(amount=2),
    ))
    detail = modal.apply(_ctx(game, target_player_idx=1, selected_mode=2))
    assert 'drained 2' in detail
    assert game.players[1].life == 18
    assert game.players[0].life == 22


def test_surveil_puts_cards_in_graveyard():
    """Surveil mills the top of the controller's library."""
    game = fresh_game()
    add_to_library(make_instant('Top'), 0, game.zones)
    detail = Surveil(count=1).apply(_ctx(game))
    assert 'surveiled 1' in detail
    assert len(game.zones.player_zones[0].graveyard) == 1


def test_discard_cards_from_controller_hand():
    """DiscardCards removes cards from the chosen player's hand."""
    game = fresh_game()
    game.zones.player_zones[0].hand.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Hand Card')),
    )
    detail = DiscardCards(count=1, target='controller').apply(_ctx(game))
    assert 'discarded Hand Card' in detail
    assert len(game.zones.player_zones[0].hand) == 0


def test_create_token_puts_permanent_on_battlefield():
    """CreateToken enters a token permanent for the controller."""
    game = fresh_game()
    blueprint = TokenBlueprint(
        name='Soldier Token',
        type_line='Creature — Soldier',
        power='1',
        toughness='1',
        colors=['W'],
    )
    detail = CreateToken(blueprint=blueprint).apply(_ctx(game))
    assert 'created Soldier Token' in detail
    assert len(game.zones.battlefield) == 1


def test_lose_life_each_opponent_in_two_player_game():
    """LoseLifeEachOpponent reduces the opponent's life in a duel."""
    game = fresh_game()
    detail = LoseLifeEachOpponent(amount=3).apply(_ctx(game))
    assert 'each opponent lost 3 life' in detail
    assert game.players[1].life == 17


def test_effect_serde_roundtrip_scry_and_surveil():
    """Scry and Surveil survive JSON serialization."""
    for effect in (Scry(count=2), Surveil(count=3)):
        restored = effect_from_dict(effect_to_dict(effect))
        assert restored == effect


def test_effect_serde_roundtrip_effect_list_gain_life_and_modal():
    """EffectList, GainLife, and nested Modal survive JSON serialization."""
    samples = (
        GainLife(amount=3),
        EffectList((Scry(count=1), DrawCards(count=1))),
        Modal(modes=(DealDamage(amount=3), DestroyPermanent())),
    )
    for effect in samples:
        restored = effect_from_dict(effect_to_dict(effect))
        assert restored == effect


def test_delirium_deal_damage_uses_higher_amount_with_delirium():
    """DeliriumDealDamage deals more when four graveyard types are met."""
    game = fresh_game()
    for type_line in ('Creature', 'Instant', 'Sorcery', 'Artifact'):
        game.zones.player_zones[0].graveyard.append(
            CardObject(
                controller_idx=0,
                owner_idx=0,
                card_info=make_card(name=type_line, type_line=type_line),
            ),
        )
    detail = DeliriumDealDamage(base_amount=2, delirium_amount=6).apply(_ctx(game))
    assert 'dealt 6' in detail
    assert game.players[1].life == 14


def test_fight_creatures_deal_damage_to_each_other():
    """FightCreatures exchanges power-based damage between two targets."""
    game = fresh_game()
    attacker = make_creature('Attacker', power=3, toughness=3)
    blocker = make_creature('Blocker', power=2, toughness=4)
    place_on_battlefield(attacker, 0, game.zones)
    place_on_battlefield(blocker, 1, game.zones)
    perm_a = game.zones.battlefield[0]
    perm_b = game.zones.battlefield[1]
    ctx = CardEffectContext(
        game=game,
        controller_idx=0,
        source=_card('Fight Spell'),
        targets=_CardEffectTargets(
            creature_uid=str(perm_a.obj_id),
            second_creature_uid=str(perm_b.obj_id),
        ),
    )
    detail = FightCreatures().apply(ctx)
    assert 'fought' in detail
    assert perm_a.damage_marked == 2
    assert perm_b.damage_marked == 3
