"""Trigger conditions for wired ability words."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.core.game_object import (
    CardObject,
    Permanent,
    effective_power,
    effective_toughness,
)
from engine.core.zones import Zone, ZoneMoveEvent
from engine.rules.triggers import (
    AttackTriggerEvent,
    CombatDamageTriggerEvent,
    MassAttackTriggerEvent,
    SpellCastTriggerEvent,
    StepTriggerEvent,
    TriggerDefinition,
    TriggerEvent,
)
from engine.core.turn_structure import Step, is_main_phase
from engine.rules.trigger_predicates import (
    is_controller_creature_enters_battlefield,
    is_source_enters_battlefield,
)

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def is_controller_creature_enters(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Rally: a creature entered the battlefield under your control."""
    return is_controller_creature_enters_battlefield(event, definition)


def is_controller_land_enters(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Landfall: a land entered the battlefield under your control."""
    return (
        isinstance(event, ZoneMoveEvent)
        and event.to_zone == Zone.BATTLEFIELD
        and isinstance(event.obj, Permanent)
        and 'Land' in event.obj.type_line
        and event.player_idx == definition.controller_idx
    )


def is_controller_enchantment_enters(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Constellation: an enchantment entered under your control."""
    return (
        isinstance(event, ZoneMoveEvent)
        and event.to_zone == Zone.BATTLEFIELD
        and isinstance(event.obj, Permanent)
        and 'Enchantment' in event.obj.type_line
        and event.player_idx == definition.controller_idx
    )


def is_raid_at_beginning_of_combat(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Raid: beginning of combat if an opponent was dealt damage this turn."""
    opponent = 1 - definition.controller_idx
    return (
        isinstance(event, StepTriggerEvent)
        and event.step == Step.BEGIN_COMBAT
        and event.active_player_idx == definition.controller_idx
        and game.players[opponent].was_dealt_damage_this_turn
    )


def is_controller_instant_or_sorcery_cast(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Magecraft: you cast an instant or sorcery spell."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and (
            'Instant' in event.type_line
            or 'Sorcery' in event.type_line
        )
    )


def is_source_enraged(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Enrage: this creature was dealt damage."""
    return (
        isinstance(event, CombatDamageTriggerEvent)
        and event.damaged_permanent_id == definition.source_permanent_id
        and event.amount > 0
    )


def _source_attacker(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> Permanent | None:
    """Return the source permanent if it is the attacker, else None."""
    if not isinstance(event, AttackTriggerEvent):
        return None
    if event.attacker_id != definition.source_permanent_id:
        return None
    return game.zones.find_permanent(definition.source_permanent_id)


def _is_source_enters_battlefield(
    event: TriggerEvent,
    definition: TriggerDefinition,
) -> bool:
    """Return True when this permanent entered the battlefield."""
    return is_source_enters_battlefield(event, definition)


def _artifact_count(game: GameState, player_idx: int) -> int:
    return sum(
        1
        for perm in game.zones.battlefield
        if perm.controller_idx == player_idx and 'Artifact' in perm.type_line
    )


def _graveyard_size(game: GameState, player_idx: int) -> int:
    return len(game.zones.player_zones[player_idx].graveyard)


def _creature_cards_in_graveyard(game: GameState, player_idx: int) -> int:
    count = 0
    for card in game.zones.player_zones[player_idx].graveyard:
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        if 'Creature' in card.card_info.type_line:
            count += 1
    return count


def _domain_count(game: GameState, player_idx: int) -> int:
    basic_types = ('Plains', 'Island', 'Swamp', 'Mountain', 'Forest')
    found: set[str] = set()
    for perm in game.zones.battlefield:
        if perm.controller_idx != player_idx or 'Land' not in perm.type_line:
            continue
        for label in basic_types:
            if label in perm.type_line:
                found.add(label)
    return len(found)


def _delirium_met(game: GameState, player_idx: int) -> bool:
    types: set[str] = set()
    for card in game.zones.player_zones[player_idx].graveyard:
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        type_line = card.card_info.type_line
        for label in (
            'Creature',
            'Instant',
            'Sorcery',
            'Artifact',
            'Enchantment',
            'Land',
            'Planeswalker',
            'Battle',
        ):
            if label in type_line:
                types.add(label.lower())
    return len(types) >= 4


def is_source_etb_metalcraft(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Metalcraft: this permanent entered and you control three or more artifacts."""
    return (
        _is_source_enters_battlefield(event, definition)
        and _artifact_count(game, definition.controller_idx) >= 3
    )


def is_source_etb_delirium(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Delirium: this permanent entered with four or more card types in graveyard."""
    return (
        _is_source_enters_battlefield(event, definition)
        and _delirium_met(game, definition.controller_idx)
    )


def is_battalion_mass_attack(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Battalion: you attacked with three or more creatures."""
    return (
        isinstance(event, MassAttackTriggerEvent)
        and event.attacking_player_idx == definition.controller_idx
        and event.attacker_count >= 3
    )


def _max_creature_power(game: GameState, player_idx: int) -> int:
    powers = [
        effective_power(perm)
        for perm in game.zones.battlefield
        if perm.controller_idx == player_idx and 'Creature' in perm.type_line
    ]
    return max(powers) if powers else 0


def _is_controller_cast_after_death(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Return True when the controller cast a spell and a creature died this turn."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and game.creature_died_this_turn
    )


def is_morbid_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Morbid: you cast a spell and a creature died this turn."""
    return _is_controller_cast_after_death(event, game, definition)


def is_ferocious_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Ferocious: you cast a spell while controlling a power-4+ creature."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _max_creature_power(game, definition.controller_idx) >= 4
    )


def is_formidable_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Formidable: you cast a spell while controlling a power-8+ creature."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _max_creature_power(game, definition.controller_idx) >= 8
    )


def is_source_etb_revolt(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Revolt: this permanent entered after you controlled a permanent leaving."""
    return (
        _is_source_enters_battlefield(event, definition)
        and game.players[definition.controller_idx].revolt_this_turn
    )


def is_source_inspired_attack(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Inspired: this creature attacked."""
    return (
        isinstance(event, AttackTriggerEvent)
        and event.attacker_id == definition.source_permanent_id
    )


def is_hellbent_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Hellbent: you cast a spell while you have no cards in hand."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and not game.zones.player_zones[definition.controller_idx].hand
    )


def is_threshold_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Threshold: you cast a spell with seven or more cards in your graveyard."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _graveyard_size(game, definition.controller_idx) >= 7
    )


def is_source_etb_threshold(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Threshold: this permanent entered with seven or more cards in graveyard."""
    return (
        _is_source_enters_battlefield(event, definition)
        and _graveyard_size(game, definition.controller_idx) >= 7
    )


def is_undergrowth_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Undergrowth: you cast a spell with creature cards in your graveyard."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _creature_cards_in_graveyard(game, definition.controller_idx) > 0
    )


def is_domain_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Domain: you cast a spell while controlling a basic land type."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _domain_count(game, definition.controller_idx) > 0
    )


def _distinct_creature_powers(game: GameState, player_idx: int) -> int:
    powers = {
        effective_power(perm)
        for perm in game.zones.battlefield
        if perm.controller_idx == player_idx and 'Creature' in perm.type_line
    }
    return len(powers)


def is_coven_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Coven: you cast a spell while controlling three+ creatures with different powers."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _distinct_creature_powers(game, definition.controller_idx) >= 3
    )


def is_strive_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Strive: you cast a spell targeting two or more targets."""
    del game
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and len(event.targets) >= 2
    )


def is_addendum_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Addendum: you cast a spell during your main phase."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and is_main_phase(game.turn.current_step)
    )


def is_celebration_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Celebration: you cast a spell after two+ permanents entered this turn."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and game.players[definition.controller_idx].permanents_entered_this_turn >= 2
    )


def is_pack_tactics_attack(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Pack tactics: this creature attacks with a bigger ally."""
    source = _source_attacker(event, game, definition)
    if source is None:
        return False
    source_power = effective_power(source)
    source_toughness = effective_toughness(source)
    for perm in game.zones.battlefield:
        if perm.controller_idx != definition.controller_idx:
            continue
        if perm.obj_id == source.obj_id or 'Creature' not in perm.type_line:
            continue
        if effective_power(perm) > source_power:
            return True
        if effective_toughness(perm) > source_toughness:
            return True
    return False


def is_parley_at_beginning_of_combat(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Parley: beginning of combat on your turn."""
    return (
        isinstance(event, StepTriggerEvent)
        and event.step == Step.BEGIN_COMBAT
        and event.active_player_idx == definition.controller_idx
    )


def is_alliance_ally_enters(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Alliance: another Ally entered under your control."""
    return (
        isinstance(event, ZoneMoveEvent)
        and event.to_zone == Zone.BATTLEFIELD
        and isinstance(event.obj, Permanent)
        and 'Ally' in event.obj.type_line
        and event.player_idx == definition.controller_idx
        and event.obj.obj_id != definition.source_permanent_id
    )


def _colors_among_permanents(game: GameState, player_idx: int) -> int:
    """Count distinct mana colors among permanents (simplified converge)."""
    colors: set[str] = set()
    for perm in game.zones.battlefield:
        if perm.controller_idx != player_idx or perm.card_info is None:
            continue
        for letter in 'WUBRG':
            if f'{{{letter}}}' in (perm.card_info.mana_cost or '').upper():
                colors.add(letter)
    return len(colors)


def is_converge_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Converge: you cast a spell (X = colors among permanents you control)."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _colors_among_permanents(game, definition.controller_idx) > 0
    )


def is_adamant_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Adamant: you cast a spell during your main phase."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and is_main_phase(game.turn.current_step)
    )


def _chroma_count(mana_cost: str) -> int:
    colors: set[str] = set()
    upper = (mana_cost or '').upper()
    for letter in 'WUBRG':
        if f'{{{letter}}}' in upper:
            colors.add(letter)
    return len(colors)


def is_chroma_spell_cast(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Chroma: you cast a spell (X = colors in its mana cost)."""
    del game
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and _chroma_count(event.mana_cost) > 0
    )
