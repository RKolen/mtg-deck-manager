"""
Keyword registry and rules hooks (Phase E11).

Package layout (keep each file under ~1000 lines):

  registry_data.py   generated Scryfall catalog (359 entries)
  registry.py        detection API
  _core.py           has_keyword, list_keywords
  combat.py          evasion + combat damage keywords
  targeting.py       hexproof, shroud, ward, protection
  timing.py          haste, flash
  counters.py        infect, persist, undying, indestructible, ...
  handlers.py        combat damage application, regeneration, storm
  casting/           cast modifiers (flashback, kicker, …)
  actions.py         keyword actions (mostly Phase G effects)
  ability_words.py   trigger registration helpers
  other.py           ability_other bucket (split per keyword over time)

Import from this package only; submodule imports are for tests and codegen.
"""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword, list_keywords
from engine.abilities.keywords.combat import (
    can_attack,
    can_block,
    deals_in_first_strike_step,
    deals_in_regular_step,
    has_enough_blockers,
    has_lifelink,
    has_trample,
    landwalk_unblockable,
    legal_blocker,
    lethal_damage_needed,
    menace_requires_two_blockers,
    should_tap_attacker,
)
from engine.abilities.keywords.combat import has_deathtouch
from engine.abilities.keywords.counters import (
    has_infect,
    has_modular,
    has_persist,
    has_undying,
    has_wither,
    is_indestructible,
)
from engine.abilities.keywords.handlers import (
    apply_combat_damage_to_creature,
    consume_regeneration_shield,
    grant_regeneration_shield,
    storm_copy_count,
)
from engine.abilities.keywords.registry import (
    KeywordEntry,
    RegistrySummary,
    all_entries,
    canonical_name,
    detect_keywords,
    entries_by_length,
    entry_by_key,
    has_registered_keyword,
    keywords_by_category,
    registry_summary,
)
from engine.abilities.keywords.registry_data import KEYWORD_ENTRIES, SCRYFALL_KEYWORD_COUNT
from engine.abilities.keywords.targeting import (
    ProtectionSource,
    can_target_permanent,
    has_hexproof,
    has_protection_from,
    has_shroud,
    has_ward,
    must_pay_ward,
    pay_ward_for_target,
    protection_qualities,
    protection_source_from_card,
    protection_source_from_flags,
    ward_cost,
)
from engine.abilities.keywords.timing import enters_ready, has_flash

__all__ = [
    'KEYWORD_ENTRIES',
    'SCRYFALL_KEYWORD_COUNT',
    'KeywordEntry',
    'RegistrySummary',
    'all_entries',
    'apply_combat_damage_to_creature',
    'canonical_name',
    'can_attack',
    'can_block',
    'can_target_permanent',
    'consume_regeneration_shield',
    'deals_in_first_strike_step',
    'deals_in_regular_step',
    'detect_keywords',
    'entries_by_length',
    'entry_by_key',
    'enters_ready',
    'grant_regeneration_shield',
    'has_deathtouch',
    'has_enough_blockers',
    'has_flash',
    'has_hexproof',
    'has_infect',
    'has_keyword',
    'has_lifelink',
    'has_modular',
    'has_persist',
    'has_protection_from',
    'has_registered_keyword',
    'has_shroud',
    'has_trample',
    'has_undying',
    'has_ward',
    'has_wither',
    'is_indestructible',
    'keywords_by_category',
    'landwalk_unblockable',
    'legal_blocker',
    'lethal_damage_needed',
    'list_keywords',
    'menace_requires_two_blockers',
    'must_pay_ward',
    'pay_ward_for_target',
    'protection_qualities',
    'protection_source_from_card',
    'protection_source_from_flags',
    'ProtectionSource',
    'registry_summary',
    'should_tap_attacker',
    'storm_copy_count',
    'ward_cost',
]
