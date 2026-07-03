"""Infer structured CardEffect scripts from oracle text (Phase G).

Used when syncing deck script caches: built-in templates are preferred, then
any previously cached JSON, then a best-effort parse of the card's oracle text.
"""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.actions.fight import has_fight
from engine.abilities.keywords.actions.library import mill_count, scry_count, surveil_count
from engine.cards.effects import (
    CardEffect,
    CreateToken,
    DealDamage,
    DeliriumDealDamage,
    DestroyIfMaxManaValue,
    DestroyPermanent,
    DiscardCards,
    DrawCards,
    EffectList,
    ExilePermanent,
    FightCreatures,
    GainLife,
    LoseLifeEachOpponent,
    Mill,
    MillTarget,
    Modal,
    NoEffect,
    PumpUntilEOT,
    Scry,
    SetPowerToughnessUntilEOT,
    Surveil,
)
from engine.cards.oracle_parse import (
    parse_damage,
    parse_delirium_damage,
    parse_discard,
    parse_draw,
    parse_each_opponent_life_loss,
    parse_life_gain,
    parse_look_at_count,
    parse_modal_clauses,
    parse_pump,
    parse_token_blueprint,
    parse_token_create_count,
    spell_category,
)

_MILL_TARGET_RE = re.compile(r"target player", re.IGNORECASE)


def _clause_card(clause: str) -> CardInfo:
    return CardInfo(
        name='_clause_',
        quantity=1,
        sideboard=False,
        type_line='Instant',
        oracle_text=clause,
    )


def _infer_removal(text: str) -> CardEffect:
    if re.search(r'exile', text, re.IGNORECASE):
        return ExilePermanent()
    mana_cap = re.search(r'mana value (\d+) or less', text, re.IGNORECASE)
    if mana_cap is not None:
        return DestroyIfMaxManaValue(max_mv=int(mana_cap.group(1)))
    return DestroyPermanent()


def _infer_mill_target(text: str) -> MillTarget:
    lowered = text.lower()
    if 'each player' in lowered:
        return 'each'
    if _MILL_TARGET_RE.search(text):
        return 'target_player'
    if 'target opponent' in lowered:
        return 'opponent'
    return 'controller'


def _infer_category_effects(text: str, category: str) -> list[CardEffect]:
    effects: list[CardEffect] = []
    delirium = parse_delirium_damage(text)
    if delirium is not None:
        base_amount, delirium_amount = delirium
        effects.append(DeliriumDealDamage(
            base_amount=base_amount,
            delirium_amount=delirium_amount,
        ))
        return effects
    if has_fight(text) and category != 'burn':
        effects.append(FightCreatures())
        return effects
    if category == 'burn':
        amount = parse_damage(text)
        if amount > 0:
            effects.append(DealDamage(amount=amount))
    elif category == 'draw':
        count = parse_draw(text)
        if count > 0:
            effects.append(DrawCards(count=count))
    elif category == 'pump':
        power, toughness = parse_pump(text)
        if power or toughness:
            if 'base power and toughness' in text.lower():
                effects.append(SetPowerToughnessUntilEOT(power=power, toughness=toughness))
            else:
                effects.append(PumpUntilEOT(power=power, toughness=toughness))
    elif category == 'removal':
        effects.append(_infer_removal(text))
    return effects


def _append_supplemental_effects(effects: list[CardEffect], text: str) -> None:
    mill_amount = mill_count(text)
    if mill_amount > 0 and not any(isinstance(effect, Mill) for effect in effects):
        effects.append(Mill(count=mill_amount, target=_infer_mill_target(text)))

    scry_amount = scry_count(text)
    if scry_amount > 0 and not any(isinstance(effect, Scry) for effect in effects):
        effects.append(Scry(count=scry_amount))
    else:
        look_amount = parse_look_at_count(text)
        if look_amount > 0 and not any(isinstance(effect, Scry) for effect in effects):
            effects.append(Scry(count=look_amount))

    if has_fight(text) and not any(isinstance(effect, FightCreatures) for effect in effects):
        effects.append(FightCreatures())

    surveil_amount = surveil_count(text)
    if surveil_amount > 0 and not any(isinstance(effect, Surveil) for effect in effects):
        effects.append(Surveil(count=surveil_amount))

    discard = parse_discard(text)
    if discard is not None and not any(isinstance(effect, DiscardCards) for effect in effects):
        count, target = discard
        effects.append(DiscardCards(count=count, target=target))

    blueprint = parse_token_blueprint(text)
    token_count = parse_token_create_count(text)
    if blueprint is not None and token_count > 0:
        if not any(isinstance(effect, CreateToken) for effect in effects):
            effects.append(CreateToken(blueprint=blueprint, count=token_count))

    life_gain = parse_life_gain(text)
    if life_gain > 0 and not any(isinstance(effect, GainLife) for effect in effects):
        effects.append(GainLife(amount=life_gain))

    each_loss = parse_each_opponent_life_loss(text)
    if each_loss > 0 and not any(isinstance(effect, LoseLifeEachOpponent) for effect in effects):
        effects.append(LoseLifeEachOpponent(amount=each_loss))


def _infer_clause_effects(clause: str) -> CardEffect:
    inferred = infer_effects_from_oracle(_clause_card(clause))
    if inferred is None:
        return NoEffect(label=clause[:40])
    if len(inferred) == 1:
        return inferred[0]
    return EffectList(inferred)


def _infer_modal(text: str) -> Modal | None:
    clauses = parse_modal_clauses(text)
    if clauses is None:
        return None
    return Modal(modes=tuple(_infer_clause_effects(clause) for clause in clauses))


def infer_effects_from_oracle(card: CardInfo) -> tuple[CardEffect, ...] | None:
    """Return inferred effects for a noncreature spell, or None when unknown."""
    if card.is_land or card.is_creature:
        return None
    text = card.oracle_text or ''
    if not text.strip():
        return None

    effects: list[CardEffect] = []
    modal = _infer_modal(text)
    if modal is not None:
        prefix = re.split(r'choose (?:one|two|up to one)', text, maxsplit=1, flags=re.I)[0]
        _append_supplemental_effects(effects, prefix)
        effects.append(modal)
        return tuple(effects)

    category = spell_category(card)
    effects.extend(_infer_category_effects(text, category))
    _append_supplemental_effects(effects, text)
    return tuple(effects) if effects else None
