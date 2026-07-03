"""Serialize and deserialize CardEffect objects for deck script JSON."""

from __future__ import annotations

from typing import Any, Callable

from engine.cards.effects import (
    CardEffect,
    CreateToken,
    DealDamage,
    DestroyIfMaxManaValue,
    DestroyPermanent,
    DiscardCards,
    DrainLife,
    DrawCards,
    EffectList,
    ExilePermanent,
    GainLife,
    LoseLifeEachOpponent,
    Mill,
    Modal,
    NoEffect,
    PumpUntilEOT,
    Scry,
    SetPowerToughnessUntilEOT,
    Surveil,
    TreasureHunt,
)
from engine.cards.oracle_parse import TokenBlueprint

EffectDict = dict[str, Any]
EffectBuilder = Callable[[EffectDict], CardEffect]


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


_EFFECT_BUILDERS: dict[str, EffectBuilder] = {
    'CreateToken': _create_token,
    'DealDamage': lambda d: DealDamage(
        amount=int(d['amount']),
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
    'TreasureHunt': lambda _: TreasureHunt(),
}


def effect_to_dict(effect: CardEffect) -> EffectDict:  # pylint: disable=too-many-return-statements,too-many-branches
    """Convert a CardEffect to a JSON-serializable dict."""
    if isinstance(effect, CreateToken):
        return {
            'type': 'CreateToken',
            'count': effect.count,
            'blueprint': _token_blueprint_to_dict(effect.blueprint),
        }
    if isinstance(effect, DealDamage):
        return {
            'type': 'DealDamage',
            'amount': effect.amount,
            'player_target': effect.player_target,
        }
    if isinstance(effect, DestroyIfMaxManaValue):
        return {'type': 'DestroyIfMaxManaValue', 'max_mv': effect.max_mv}
    if isinstance(effect, DestroyPermanent):
        return {'type': 'DestroyPermanent'}
    if isinstance(effect, DiscardCards):
        return {
            'type': 'DiscardCards',
            'count': effect.count,
            'target': effect.target,
        }
    if isinstance(effect, DrainLife):
        return {'type': 'DrainLife', 'amount': effect.amount, 'target': effect.target}
    if isinstance(effect, DrawCards):
        return {'type': 'DrawCards', 'count': effect.count}
    if isinstance(effect, ExilePermanent):
        return {'type': 'ExilePermanent'}
    if isinstance(effect, GainLife):
        return {'type': 'GainLife', 'amount': effect.amount}
    if isinstance(effect, LoseLifeEachOpponent):
        return {'type': 'LoseLifeEachOpponent', 'amount': effect.amount}
    if isinstance(effect, Mill):
        return {'type': 'Mill', 'count': effect.count, 'target': effect.target}
    if isinstance(effect, Modal):
        return {'type': 'Modal', 'modes': [effect_to_dict(mode) for mode in effect.modes]}
    if isinstance(effect, NoEffect):
        return {'type': 'NoEffect', 'label': effect.label}
    if isinstance(effect, PumpUntilEOT):
        return {
            'type': 'PumpUntilEOT',
            'power': effect.power,
            'toughness': effect.toughness,
        }
    if isinstance(effect, Scry):
        return {
            'type': 'Scry',
            'count': effect.count,
            'bottom_indices': list(effect.bottom_indices),
        }
    if isinstance(effect, SetPowerToughnessUntilEOT):
        return {
            'type': 'SetPowerToughnessUntilEOT',
            'power': effect.power,
            'toughness': effect.toughness,
        }
    if isinstance(effect, Surveil):
        return {'type': 'Surveil', 'count': effect.count}
    if isinstance(effect, TreasureHunt):
        return {'type': 'TreasureHunt'}
    if isinstance(effect, EffectList):
        return {
            'type': 'EffectList',
            'effects': [effect_to_dict(child) for child in effect.effects],
        }
    raise TypeError(f'unsupported effect type: {type(effect).__name__}')


def effect_from_dict(data: EffectDict) -> CardEffect:
    """Build a CardEffect from a JSON dict."""
    effect_type = data['type']
    if effect_type == 'EffectList':
        return EffectList(tuple(effect_from_dict(child) for child in data['effects']))
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
