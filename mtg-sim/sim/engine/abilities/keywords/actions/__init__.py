"""
Keyword actions (72 Scryfall entries): Mill, Scry, Fight, Surveil, Proliferate, ...

Detection uses the shared registry; resolution lives in resolve.py and submodules.
"""

from __future__ import annotations

from engine.abilities.keywords.actions.detect import (
    ALL_KEYWORD_ACTIONS,
    has_keyword_action,
    keyword_actions_in_oracle,
)
from engine.abilities.keywords.actions.fight import (
    combat_power,
    fight_creatures,
    has_fight,
)
from engine.abilities.keywords.actions.library import (
    discover_from_library,
    fateseal_cards,
    has_discover,
    has_fateseal,
    has_mill,
    has_scry,
    has_manifest,
    has_seek,
    has_shuffle,
    has_surveil,
    manifest_top_of_library,
    mill_cards,
    mill_count,
    scry_cards,
    scry_count,
    seek_card,
    shuffle_library,
    surveil_cards,
    surveil_count,
)
from engine.abilities.keywords.actions.counters import (
    bolster_amount,
    has_bolster,
    has_counter_action,
    has_proliferate,
    has_support,
    proliferate,
    put_plus_counters,
)
from engine.abilities.keywords.actions.resolve import (
    ActionContext,
    resolve_keyword_actions,
    resolve_spell_keyword_actions,
)
from engine.abilities.keywords.actions.tokens import (
    has_connive,
    has_create,
    has_explore,
    has_food,
    has_investigate,
    has_populate,
    has_treasure,
)

__all__ = [
    'ALL_KEYWORD_ACTIONS',
    'ActionContext',
    'combat_power',
    'discover_from_library',
    'fateseal_cards',
    'fight_creatures',
    'has_bolster',
    'has_connive',
    'has_counter_action',
    'has_create',
    'has_discover',
    'has_explore',
    'has_fateseal',
    'has_fight',
    'has_food',
    'has_investigate',
    'has_keyword_action',
    'has_mill',
    'has_populate',
    'has_proliferate',
    'has_manifest',
    'has_scry',
    'has_seek',
    'has_shuffle',
    'has_support',
    'has_surveil',
    'has_treasure',
    'bolster_amount',
    'keyword_actions_in_oracle',
    'mill_cards',
    'mill_count',
    'proliferate',
    'put_plus_counters',
    'resolve_keyword_actions',
    'resolve_spell_keyword_actions',
    'scry_cards',
    'scry_count',
    'seek_card',
    'manifest_top_of_library',
    'shuffle_library',
    'surveil_cards',
    'surveil_count',
]
