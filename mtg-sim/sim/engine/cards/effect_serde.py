"""Serialize and deserialize CardEffect objects for deck script JSON."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from engine.cards.effects import (
    CardEffect,
    CreateToken,
    DealDamage,
    DeliriumDealDamage,
    DestroyIfMaxManaValue,
    DestroyPermanent,
    DiscardCards,
    DrainLife,
    DrawCards,
    EffectList,
    ExilePermanent,
    FightCreatures,
    GainLife,
    LoseLifeEachOpponent,
    Mill,
    Modal,
    NoEffect,
    PumpUntilEOT,
    Scry,
    SetPowerToughnessUntilEOT,
    Surveil,
    SwitchPowerToughnessUntilEOT,
    TreasureHunt,
)
from engine.cards.oracle_parse import TokenBlueprint

EffectDict = dict[str, Any]
EffectBuilder = Callable[[EffectDict], CardEffect]
EffectSerializer = Callable[[Any], EffectDict]


def _token_blueprint_to_dict(blueprint: TokenBlueprint) -> dict[str, Any]:
    return {
        'name': blueprint.name,
        'type_line': blueprint.type_line,
        'power': blueprint.power,
        'toughness': blueprint.toughness,
        'colors': list(blueprint.colors),
        'oracle_text': blueprint.oracle_text,
    }


def _token_blueprint_from_dict(data: dict[str, Any]) -> TokenBlueprint:
    return TokenBlueprint(
        name=str(data['name']),
        type_line=str(data['type_line']),
        power=str(data['power']),
        toughness=str(data['toughness']),
        colors=[str(color) for color in (data.get('colors') or [])],
        oracle_text=str(data.get('oracle_text', '')),
    )


def _mill(data: EffectDict) -> CardEffect:
    return Mill(count=int(data['count']), target=data.get('target', 'controller'))


def _modal(data: EffectDict) -> CardEffect:
    return Modal(modes=tuple(effect_from_dict(mode) for mode in data['modes']))


def _create_token(data: EffectDict) -> CardEffect:
    return CreateToken(
        blueprint=_token_blueprint_from_dict(data['blueprint']),
        count=int(data.get('count', 1)),
    )


def _serialize_create_token(effect: CreateToken) -> EffectDict:
    return {
        'type': 'CreateToken',
        'count': effect.count,
        'blueprint': _token_blueprint_to_dict(effect.blueprint),
    }


def _serialize_deal_damage(effect: DealDamage) -> EffectDict:
    return {
        'type': 'DealDamage',
        'amount': effect.amount,
        'player_target': effect.player_target,
    }


def _serialize_delirium_deal_damage(effect: DeliriumDealDamage) -> EffectDict:
    return {
        'type': 'DeliriumDealDamage',
        'base_amount': effect.base_amount,
        'delirium_amount': effect.delirium_amount,
        'player_target': effect.player_target,
    }


def _serialize_discard_cards(effect: DiscardCards) -> EffectDict:
    return {
        'type': 'DiscardCards',
        'count': effect.count,
        'target': effect.target,
    }


def _serialize_drain_life(effect: DrainLife) -> EffectDict:
    return {'type': 'DrainLife', 'amount': effect.amount, 'target': effect.target}


def _serialize_draw_cards(effect: DrawCards) -> EffectDict:
    return {'type': 'DrawCards', 'count': effect.count}


def _serialize_mill(effect: Mill) -> EffectDict:
    return {'type': 'Mill', 'count': effect.count, 'target': effect.target}


def _serialize_modal(effect: Modal) -> EffectDict:
    return {'type': 'Modal', 'modes': [effect_to_dict(mode) for mode in effect.modes]}


def _serialize_no_effect(effect: NoEffect) -> EffectDict:
    return {'type': 'NoEffect', 'label': effect.label}


def _serialize_pump_until_eot(effect: PumpUntilEOT) -> EffectDict:
    return {
        'type': 'PumpUntilEOT',
        'power': effect.power,
        'toughness': effect.toughness,
    }


def _serialize_scry(effect: Scry) -> EffectDict:
    return {
        'type': 'Scry',
        'count': effect.count,
        'bottom_indices': list(effect.bottom_indices),
    }


def _serialize_set_pt_until_eot(effect: SetPowerToughnessUntilEOT) -> EffectDict:
    return {
        'type': 'SetPowerToughnessUntilEOT',
        'power': effect.power,
        'toughness': effect.toughness,
    }


def _serialize_switch_pt_until_eot(_effect: SwitchPowerToughnessUntilEOT) -> EffectDict:
    return {'type': 'SwitchPowerToughnessUntilEOT'}


def _serialize_destroy_if_max_mv(effect: DestroyIfMaxManaValue) -> EffectDict:
    return {'type': 'DestroyIfMaxManaValue', 'max_mv': effect.max_mv}


def _serialize_gain_life(effect: GainLife) -> EffectDict:
    return {'type': 'GainLife', 'amount': effect.amount}


def _serialize_lose_life_each_opponent(effect: LoseLifeEachOpponent) -> EffectDict:
    return {'type': 'LoseLifeEachOpponent', 'amount': effect.amount}


def _serialize_surveil(effect: Surveil) -> EffectDict:
    return {'type': 'Surveil', 'count': effect.count}


def _serialize_effect_list(effect: EffectList) -> EffectDict:
    return {
        'type': 'EffectList',
        'effects': [effect_to_dict(child) for child in effect.effects],
    }


_EFFECT_BUILDERS: dict[str, EffectBuilder] = {
    'CreateToken': _create_token,
    'DealDamage': lambda d: DealDamage(
        amount=int(d['amount']),
        player_target=d.get('player_target', 'opponent'),
    ),
    'DeliriumDealDamage': lambda d: DeliriumDealDamage(
        base_amount=int(d['base_amount']),
        delirium_amount=int(d['delirium_amount']),
        player_target=d.get('player_target', 'opponent'),
    ),
    'DestroyIfMaxManaValue': lambda d: DestroyIfMaxManaValue(max_mv=int(d['max_mv'])),
    'DestroyPermanent': lambda _: DestroyPermanent(),
    'DiscardCards': lambda d: DiscardCards(
        count=int(d['count']),
        target=d.get('target', 'controller'),
    ),
    'DrainLife': lambda d: DrainLife(
        amount=int(d['amount']),
        target=d.get('target', 'target_player'),
    ),
    'DrawCards': lambda d: DrawCards(count=int(d['count'])),
    'ExilePermanent': lambda _: ExilePermanent(),
    'FightCreatures': lambda _: FightCreatures(),
    'GainLife': lambda d: GainLife(amount=int(d['amount'])),
    'LoseLifeEachOpponent': lambda d: LoseLifeEachOpponent(amount=int(d['amount'])),
    'Mill': _mill,
    'Modal': _modal,
    'NoEffect': lambda d: NoEffect(label=str(d.get('label', ''))),
    'PumpUntilEOT': lambda d: PumpUntilEOT(
        power=int(d['power']),
        toughness=int(d['toughness']),
    ),
    'Scry': lambda d: Scry(
        count=int(d['count']),
        bottom_indices=tuple(int(idx) for idx in (d.get('bottom_indices') or [])),
    ),
    'SetPowerToughnessUntilEOT': lambda d: SetPowerToughnessUntilEOT(
        power=int(d['power']),
        toughness=int(d['toughness']),
    ),
    'Surveil': lambda d: Surveil(count=int(d['count'])),
    'SwitchPowerToughnessUntilEOT': lambda _: SwitchPowerToughnessUntilEOT(),
    'TreasureHunt': lambda _: TreasureHunt(),
}

_EFFECT_SERIALIZERS: dict[type[CardEffect], EffectSerializer] = {
    CreateToken: _serialize_create_token,
    DealDamage: _serialize_deal_damage,
    DeliriumDealDamage: _serialize_delirium_deal_damage,
    DestroyIfMaxManaValue: _serialize_destroy_if_max_mv,
    DestroyPermanent: lambda _: {'type': 'DestroyPermanent'},
    DiscardCards: _serialize_discard_cards,
    DrainLife: _serialize_drain_life,
    DrawCards: _serialize_draw_cards,
    ExilePermanent: lambda _: {'type': 'ExilePermanent'},
    FightCreatures: lambda _: {'type': 'FightCreatures'},
    GainLife: _serialize_gain_life,
    LoseLifeEachOpponent: _serialize_lose_life_each_opponent,
    Mill: _serialize_mill,
    Modal: _serialize_modal,
    NoEffect: _serialize_no_effect,
    PumpUntilEOT: _serialize_pump_until_eot,
    Scry: _serialize_scry,
    SetPowerToughnessUntilEOT: _serialize_set_pt_until_eot,
    Surveil: _serialize_surveil,
    SwitchPowerToughnessUntilEOT: _serialize_switch_pt_until_eot,
    TreasureHunt: lambda _: {'type': 'TreasureHunt'},
    EffectList: _serialize_effect_list,
}

ALLOWED_EFFECT_TYPES: frozenset[str] = frozenset(_EFFECT_BUILDERS) | frozenset({'EffectList'})


def effect_to_dict(effect: CardEffect) -> EffectDict:
    """Convert a CardEffect to a JSON-serializable dict."""
    serializer = _EFFECT_SERIALIZERS.get(type(effect))
    if serializer is None:
        raise TypeError(f'unsupported effect type: {type(effect).__name__}')
    return serializer(effect)


def effect_from_dict(data: EffectDict) -> CardEffect:
    """Build a CardEffect from a JSON dict."""
    effect_type = data['type']
    if effect_type == 'EffectList':
        return EffectList(tuple(effect_from_dict(child) for child in data['effects']))
    if effect_type == 'draw':
        return DrawCards(count=int(data['count']))
    builder = _EFFECT_BUILDERS.get(effect_type)
    if builder is None:
        raise ValueError(f'unknown effect type: {effect_type!r}')
    return builder(data)


def effects_to_json(effects: tuple[CardEffect, ...]) -> list[EffectDict]:
    """Serialize a tuple of effects."""
    return [effect_to_dict(effect) for effect in effects]


def effects_from_json(data: list[EffectDict]) -> tuple[CardEffect, ...]:
    """Deserialize a list of effect dicts."""
    return tuple(effect_from_dict(entry) for entry in data)
