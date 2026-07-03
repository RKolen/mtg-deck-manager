"""Serialize and deserialize CardEffect objects for deck script JSON."""

from __future__ import annotations

from typing import Any, Callable

from engine.cards.effects import (
    CardEffect,
    DealDamage,
    DestroyIfMaxManaValue,
    DestroyPermanent,
    DrainLife,
    DrawCards,
    EffectList,
    ExilePermanent,
    Mill,
    Modal,
    NoEffect,
    PumpUntilEOT,
    SetPowerToughnessUntilEOT,
    TreasureHunt,
)

EffectDict = dict[str, Any]
EffectBuilder = Callable[[EffectDict], CardEffect]


def _mill(data: EffectDict) -> CardEffect:
    return Mill(count=int(data['count']), target=data.get('target', 'controller'))


def _modal(data: EffectDict) -> CardEffect:
    return Modal(modes=tuple(effect_from_dict(mode) for mode in data['modes']))


_EFFECT_BUILDERS: dict[str, EffectBuilder] = {
    'DealDamage': lambda d: DealDamage(
        amount=int(d['amount']),
        player_target=d.get('player_target', 'opponent'),
    ),
    'DestroyIfMaxManaValue': lambda d: DestroyIfMaxManaValue(max_mv=int(d['max_mv'])),
    'DestroyPermanent': lambda _: DestroyPermanent(),
    'DrainLife': lambda d: DrainLife(
        amount=int(d['amount']),
        target=d.get('target', 'target_player'),
    ),
    'DrawCards': lambda d: DrawCards(count=int(d['count'])),
    'ExilePermanent': lambda _: ExilePermanent(),
    'Mill': _mill,
    'Modal': _modal,
    'NoEffect': lambda d: NoEffect(label=str(d.get('label', ''))),
    'PumpUntilEOT': lambda d: PumpUntilEOT(
        power=int(d['power']),
        toughness=int(d['toughness']),
    ),
    'SetPowerToughnessUntilEOT': lambda d: SetPowerToughnessUntilEOT(
        power=int(d['power']),
        toughness=int(d['toughness']),
    ),
    'TreasureHunt': lambda _: TreasureHunt(),
}


def effect_to_dict(effect: CardEffect) -> EffectDict:  # pylint: disable=too-many-return-statements,too-many-branches
    """Convert a CardEffect to a JSON-serializable dict."""
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
    if isinstance(effect, DrainLife):
        return {'type': 'DrainLife', 'amount': effect.amount, 'target': effect.target}
    if isinstance(effect, DrawCards):
        return {'type': 'DrawCards', 'count': effect.count}
    if isinstance(effect, ExilePermanent):
        return {'type': 'ExilePermanent'}
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
    if isinstance(effect, SetPowerToughnessUntilEOT):
        return {
            'type': 'SetPowerToughnessUntilEOT',
            'power': effect.power,
            'toughness': effect.toughness,
        }
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
