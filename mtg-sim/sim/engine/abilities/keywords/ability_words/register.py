"""Register ability-word triggers when a permanent enters the battlefield."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from engine.abilities.keywords.ability_words.clause import clause_after_ability_word
from engine.abilities.keywords.ability_words.conditions import (
    is_battalion_mass_attack,
    is_controller_enchantment_enters,
    is_controller_instant_or_sorcery_cast,
    is_controller_land_enters,
    is_raid_at_beginning_of_combat,
    is_source_enraged,
    is_source_etb_delirium,
    is_source_etb_metalcraft,
)
from engine.abilities.keywords.ability_words.detect import has_ability_word
from engine.abilities.keywords.ability_words.effects import (
    AbilityWordEffect,
    ProwessEffect,
)
from engine.cards.oracle_parse import parse_token_blueprint
from engine.core.game_object import Permanent
from engine.game.helpers import CreateTokenEffect
from engine.rules.triggers import (
    TriggerCondition,
    TriggerKey,
    TriggerRegistry,
    is_noncreature_nonland_spell_cast,
    is_spell_targeting_source,
)

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class _AbilityWordWire:
    """Maps one ability word to a trigger key and condition."""

    trigger_key: TriggerKey
    condition: TriggerCondition


_WIRED: dict[str, _AbilityWordWire] = {
    'Landfall': _AbilityWordWire(TriggerKey.ENTERS_BATTLEFIELD, is_controller_land_enters),
    'Constellation': _AbilityWordWire(
        TriggerKey.ENTERS_BATTLEFIELD,
        is_controller_enchantment_enters,
    ),
    'Raid': _AbilityWordWire(TriggerKey.BEGINNING_OF_COMBAT, is_raid_at_beginning_of_combat),
    'Magecraft': _AbilityWordWire(TriggerKey.SPELL_CAST, is_controller_instant_or_sorcery_cast),
    'Enrage': _AbilityWordWire(
        TriggerKey.DEALS_COMBAT_DAMAGE,
        is_source_enraged,
    ),
    'Battalion': _AbilityWordWire(TriggerKey.MASS_ATTACK, is_battalion_mass_attack),
    'Metalcraft': _AbilityWordWire(
        TriggerKey.ENTERS_BATTLEFIELD,
        is_source_etb_metalcraft,
    ),
    'Delirium': _AbilityWordWire(
        TriggerKey.ENTERS_BATTLEFIELD,
        is_source_etb_delirium,
    ),
}


def register_permanent_ability_words(
    permanent: Permanent,
    registry: TriggerRegistry,
) -> None:
    """Scan oracle text and register triggers for wired ability words."""
    oracle = permanent.oracle_text or ''
    if not oracle:
        return

    for word, wire in _WIRED.items():
        if not has_ability_word(oracle, word):
            continue
        clause = clause_after_ability_word(oracle, word)
        effect = AbilityWordEffect(clause) if clause else None
        registry.register(
            permanent,
            wire.trigger_key,
            wire.condition,
            effect=effect,
        )

    _register_heroic(permanent, registry, oracle)
    _register_prowess(permanent, registry, oracle)


def _register_heroic(
    permanent: Permanent,
    registry: TriggerRegistry,
    oracle: str,
) -> None:
    """Heroic: spell cast targeting this permanent creates a token."""
    if not has_ability_word(oracle, 'Heroic'):
        return
    blueprint = parse_token_blueprint(oracle)
    effect = CreateTokenEffect(blueprint) if blueprint is not None else None
    registry.register(
        permanent,
        TriggerKey.SPELL_CAST,
        is_spell_targeting_source,
        effect=effect,
    )


def _register_prowess(
    permanent: Permanent,
    registry: TriggerRegistry,
    oracle: str,
) -> None:
    """Prowess: noncreature spell cast gives +1/+1."""
    if not has_ability_word(oracle, 'Prowess'):
        return
    registry.register(
        permanent,
        TriggerKey.SPELL_CAST,
        is_noncreature_nonland_spell_cast,
        effect=ProwessEffect(),
    )
