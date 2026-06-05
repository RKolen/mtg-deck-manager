"""Extended trigger conditions for wired ability words (continuation of conditions.py)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.core.game_object import CardObject, Permanent
from engine.core.zones import Zone, ZoneMoveEvent
from engine.rules.triggers import (
    AttackTriggerEvent,
    SpellCastTriggerEvent,
    StepTriggerEvent,
    TriggerDefinition,
    TriggerEvent,
)
from engine.core.turn_structure import Step
from engine.rules.trigger_predicates import is_controller_creature_enters_battlefield
from engine.abilities.keywords.ability_words.conditions import (
    _graveyard_size,
    _is_controller_cast_after_death,
    _is_source_enters_battlefield,
    _source_attacker,
    is_controller_instant_or_sorcery_cast,
)

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def is_renew_creature_leaves(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Renew: another creature you control left the battlefield."""
    return (
        isinstance(event, ZoneMoveEvent)
        and event.from_zone == Zone.BATTLEFIELD
        and isinstance(event.obj, Permanent)
        and 'Creature' in event.obj.type_line
        and event.obj.controller_idx == definition.controller_idx
        and event.obj.obj_id != definition.source_permanent_id
    )


def is_valiant_first_attack(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Valiant: this creature attacks for the first time this turn."""
    source = _source_attacker(event, game, definition)
    if source is None:
        return False
    return not source.counters.get('valiant_this_turn')


def is_eerie_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Eerie: you cast a spell while controlling an enchantment."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and any(
            perm.controller_idx == definition.controller_idx
            and 'Enchantment' in perm.type_line
            for perm in game.zones.battlefield
        )
    )


def is_lieutenant_etb(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Lieutenant: this entered while you control a legendary creature."""
    if not _is_source_enters_battlefield(event, definition):
        return False
    return any(
        perm.controller_idx == definition.controller_idx
        and perm.obj_id != definition.source_permanent_id
        and 'Legendary' in perm.type_line
        and 'Creature' in perm.type_line
        for perm in game.zones.battlefield
    )


def is_kinship_upkeep(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Kinship: beginning of upkeep on your turn."""
    del game
    return (
        isinstance(event, StepTriggerEvent)
        and event.step == Step.UPKEEP
        and event.active_player_idx == definition.controller_idx
    )


def is_flurry_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Flurry: you cast your second or later spell this turn."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and game.players[definition.controller_idx].spells_cast_this_turn >= 2
    )


def is_fateful_hour_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Fateful hour: you cast a spell while you have 5 or less life."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and game.players[definition.controller_idx].life <= 5
    )


def is_spell_mastery_spell_cast(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Spell mastery: you cast an instant or sorcery spell."""
    return is_controller_instant_or_sorcery_cast(event, _game, definition)


def is_grandeur_upkeep(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Grandeur: beginning of upkeep with a legendary card in hand."""
    if not (
        isinstance(event, StepTriggerEvent)
        and event.step == Step.UPKEEP
        and event.active_player_idx == definition.controller_idx
    ):
        return False
    hand = game.zones.player_zones[definition.controller_idx].hand
    for card in hand:
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        if 'Legendary' in card.card_info.type_line:
            return True
    return False


def _creature_count(game: GameState, player_idx: int) -> int:
    return sum(
        1
        for perm in game.zones.battlefield
        if perm.controller_idx == player_idx and 'Creature' in perm.type_line
    )


def is_underdog_attack(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Underdog: this attacks while you control fewer creatures than an opponent."""
    source = _source_attacker(event, game, definition)
    if source is None:
        return False
    mine = _creature_count(game, definition.controller_idx)
    opponent = 1 - definition.controller_idx
    theirs = _creature_count(game, opponent)
    return mine < theirs


def is_eminence_spell_cast(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Eminence: you cast a spell while this is on the battlefield."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
    )


def _permanent_cards_in_graveyard(game: GameState, player_idx: int) -> int:
    count = 0
    for card in game.zones.player_zones[player_idx].graveyard:
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        type_line = card.card_info.type_line
        if card.card_info.is_creature:
            continue
        if any(label in type_line for label in ('Artifact', 'Enchantment', 'Land', 'Planeswalker')):
            count += 1
    return count


def is_descend_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Descend: you cast a spell with four or more permanent cards in your graveyard."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _permanent_cards_in_graveyard(game, definition.controller_idx) >= 4
    )


def is_corrupted_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Corrupted: you cast a spell while an opponent has three or more poison counters."""
    opponent = 1 - definition.controller_idx
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and game.players[opponent].poison >= 3
    )


def is_survival_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Survival: you cast a spell after a creature died this turn."""
    return _is_controller_cast_after_death(event, game, definition)


def is_start_your_engines_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Start your engines!: you cast a spell on turn four or later."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and game.turn.context.turn_number >= 4
    )


def is_legacy_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Legacy: you cast a spell while you have a legendary card in your graveyard."""
    if not (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
    ):
        return False
    for card in game.zones.player_zones[definition.controller_idx].graveyard:
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        if 'Legendary' in card.card_info.type_line:
            return True
    return False


def is_paradox_spell_cast(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Paradox: you cast a spell with mana value 7 or greater."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and event.cmc >= 7
    )


def is_radiance_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Radiance: you cast a spell while you control a white permanent."""
    if not (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
    ):
        return False
    for perm in game.zones.battlefield:
        if perm.controller_idx != definition.controller_idx:
            continue
        if perm.card_info is not None and 'W' in (perm.card_info.mana_cost or '').upper():
            return True
        if 'Plains' in perm.type_line:
            return True
    return False


def is_teamwork_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Teamwork: you cast a spell while you control two or more creatures."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _creature_count(game, definition.controller_idx) >= 2
    )


def is_vivid_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Vivid: you cast a spell while you control a land with a charge counter."""
    if not (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
    ):
        return False
    for perm in game.zones.battlefield:
        if perm.controller_idx != definition.controller_idx:
            continue
        if 'Land' not in perm.type_line:
            continue
        if perm.counters.get('charge', 0) > 0 or 'Vivid' in perm.name:
            return True
    return False


def is_void_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Void: you cast a spell while an opponent has no cards in hand."""
    opponent = 1 - definition.controller_idx
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and not game.zones.player_zones[opponent].hand
    )


def is_disappear_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Disappear: you cast a spell after an opponent was dealt damage this turn."""
    opponent = 1 - definition.controller_idx
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and game.players[opponent].was_dealt_damage_this_turn
    )


def is_infusion_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Infusion: you cast a spell while you control an artifact."""
    if not (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
    ):
        return False
    return any(
        perm.controller_idx == definition.controller_idx
        and 'Artifact' in perm.type_line
        for perm in game.zones.battlefield
    )


def is_kinfall_creature_enters(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Kinfall: a creature with power 4 or greater entered under your control."""
    return is_controller_creature_enters_battlefield(
        event,
        definition,
        min_power=4,
    )


def is_landship_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Landship: you cast a spell while you control an Island."""
    if not (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
    ):
        return False
    return any(
        perm.controller_idx == definition.controller_idx
        and 'Island' in perm.type_line
        for perm in game.zones.battlefield
    )


def is_opus_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Opus: you cast a spell while you have five or more cards in hand."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and len(game.zones.player_zones[definition.controller_idx].hand) >= 5
    )


def is_join_forces_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Join forces: you cast a spell (simplified; multiplayer not modeled)."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _creature_count(game, definition.controller_idx) >= 2
    )


def is_tempting_offer_spell_cast(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Tempting offer: you cast a spell with mana value 6 or greater."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and event.cmc >= 6
    )


def is_heros_reward_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Hero's Reward: you cast a spell after a creature died this turn."""
    return _is_controller_cast_after_death(event, game, definition)


def is_fathomless_descent_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Fathomless descent: you cast a spell with ten or more cards in your graveyard."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _graveyard_size(game, definition.controller_idx) >= 10
    )


def is_imprint_etb(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Imprint: this permanent entered the battlefield."""
    return _is_source_enters_battlefield(event, definition)


def is_repartee_opponent_attacks(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Repartee: an opponent declared an attacker."""
    opponent = 1 - definition.controller_idx
    return (
        isinstance(event, AttackTriggerEvent)
        and event.attacking_player_idx == opponent
    )


def is_sweep_spell_cast(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Sweep: you cast a spell (permanent-hosted reminder; spells use spell_words)."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
    )


def is_secret_council_spell_cast(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Secret council: you cast a spell (votes simplified)."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
    )


def is_will_of_council_spell_cast(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Will of the council: you cast a spell (votes simplified)."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
    )


def is_councils_dilemma_spell_cast(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Council's dilemma: you cast a spell (votes simplified)."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
    )


def is_will_of_planeswalkers_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Will of the Planeswalkers: you cast a spell while you control a planeswalker."""
    if not (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
    ):
        return False
    return any(
        perm.controller_idx == definition.controller_idx
        and 'Planeswalker' in perm.type_line
        for perm in game.zones.battlefield
    )
