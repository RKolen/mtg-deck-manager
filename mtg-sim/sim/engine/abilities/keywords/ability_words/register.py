"""Register ability-word triggers when a permanent enters the battlefield."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from engine.abilities.keywords.ability_words.clause import clause_after_ability_word
from engine.abilities.keywords.ability_words.conditions import (
    is_battalion_mass_attack,
    is_controller_creature_enters,
    is_controller_enchantment_enters,
    is_controller_instant_or_sorcery_cast,
    is_controller_land_enters,
    is_domain_spell_cast,
    is_ferocious_spell_cast,
    is_flurry_spell_cast,
    is_formidable_spell_cast,
    is_hellbent_spell_cast,
    is_addendum_spell_cast,
    is_adamant_spell_cast,
    is_alliance_ally_enters,
    is_celebration_spell_cast,
    is_converge_spell_cast,
    is_eerie_spell_cast,
    is_lieutenant_etb,
    is_coven_spell_cast,
    is_kinship_upkeep,
    is_morbid_spell_cast,
    is_pack_tactics_attack,
    is_parley_at_beginning_of_combat,
    is_raid_at_beginning_of_combat,
    is_strive_spell_cast,
    is_source_enraged,
    is_source_etb_delirium,
    is_source_etb_metalcraft,
    is_source_etb_revolt,
    is_source_etb_threshold,
    is_source_inspired_attack,
    is_threshold_spell_cast,
    is_undergrowth_spell_cast,
)
from engine.abilities.keywords.ability_words.detect import has_ability_word
from engine.abilities.keywords.ability_words.effects import (
    AbilityWordEffect,
    KinshipEffect,
    ParleyEffect,
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
    'Morbid': _AbilityWordWire(TriggerKey.SPELL_CAST, is_morbid_spell_cast),
    'Ferocious': _AbilityWordWire(TriggerKey.SPELL_CAST, is_ferocious_spell_cast),
    'Formidable': _AbilityWordWire(TriggerKey.SPELL_CAST, is_formidable_spell_cast),
    'Revolt': _AbilityWordWire(TriggerKey.ENTERS_BATTLEFIELD, is_source_etb_revolt),
    'Inspired': _AbilityWordWire(TriggerKey.ATTACKS, is_source_inspired_attack),
    'Rally': _AbilityWordWire(TriggerKey.ENTERS_BATTLEFIELD, is_controller_creature_enters),
    'Hellbent': _AbilityWordWire(TriggerKey.SPELL_CAST, is_hellbent_spell_cast),
    'Undergrowth': _AbilityWordWire(TriggerKey.SPELL_CAST, is_undergrowth_spell_cast),
    'Domain': _AbilityWordWire(TriggerKey.SPELL_CAST, is_domain_spell_cast),
    'Flurry': _AbilityWordWire(TriggerKey.SPELL_CAST, is_flurry_spell_cast),
    'Coven': _AbilityWordWire(TriggerKey.SPELL_CAST, is_coven_spell_cast),
    'Strive': _AbilityWordWire(TriggerKey.SPELL_CAST, is_strive_spell_cast),
    'Parley': _AbilityWordWire(TriggerKey.BEGINNING_OF_COMBAT, is_parley_at_beginning_of_combat),
    'Addendum': _AbilityWordWire(TriggerKey.SPELL_CAST, is_addendum_spell_cast),
    'Celebration': _AbilityWordWire(TriggerKey.SPELL_CAST, is_celebration_spell_cast),
    'Pack tactics': _AbilityWordWire(TriggerKey.ATTACKS, is_pack_tactics_attack),
    'Alliance': _AbilityWordWire(TriggerKey.ENTERS_BATTLEFIELD, is_alliance_ally_enters),
    'Converge': _AbilityWordWire(TriggerKey.SPELL_CAST, is_converge_spell_cast),
    'Adamant': _AbilityWordWire(TriggerKey.SPELL_CAST, is_adamant_spell_cast),
    'Kinship': _AbilityWordWire(TriggerKey.BEGINNING_OF_UPKEEP, is_kinship_upkeep),
    'Eerie': _AbilityWordWire(TriggerKey.SPELL_CAST, is_eerie_spell_cast),
    'Lieutenant': _AbilityWordWire(TriggerKey.ENTERS_BATTLEFIELD, is_lieutenant_etb),
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
        if word == 'Parley':
            registry.register(
                permanent,
                wire.trigger_key,
                wire.condition,
                effect=ParleyEffect(),
            )
            continue
        if word == 'Kinship':
            registry.register(
                permanent,
                wire.trigger_key,
                wire.condition,
                effect=KinshipEffect(),
            )
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
    _register_threshold(permanent, registry, oracle)


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


def _register_threshold(
    permanent: Permanent,
    registry: TriggerRegistry,
    oracle: str,
) -> None:
    """Threshold: spell cast or ETB with seven or more cards in graveyard."""
    if not has_ability_word(oracle, 'Threshold'):
        return
    clause = clause_after_ability_word(oracle, 'Threshold')
    effect = AbilityWordEffect(clause) if clause else None
    registry.register(
        permanent,
        TriggerKey.SPELL_CAST,
        is_threshold_spell_cast,
        effect=effect,
    )
    if 'enters the battlefield' in (clause or oracle).lower():
        registry.register(
            permanent,
            TriggerKey.ENTERS_BATTLEFIELD,
            is_source_etb_threshold,
            effect=effect,
        )
