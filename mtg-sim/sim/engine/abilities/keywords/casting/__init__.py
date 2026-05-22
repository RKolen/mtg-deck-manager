"""Cast-modifier keywords (one module per keyword as integration proceeds)."""

from engine.abilities.keywords.casting.aftermath import (
    aftermath_mana_needed,
    can_cast_aftermath,
    has_aftermath,
)
from engine.abilities.keywords.casting.escape import (
    can_cast_via_escape,
    escape_cost,
    escape_exiles_required,
    escape_mana_needed,
    escape_payment_error,
    exile_for_escape_cost,
    has_escape,
)
from engine.abilities.keywords.casting.flashback import (
    can_cast_via_flashback,
    flashback_cost,
    flashback_mana_needed,
    has_flashback,
)
from engine.abilities.keywords.casting.cascade import (
    has_cascade,
    reveal_cascade_hit,
    spell_mana_value,
)
from engine.abilities.keywords.casting.storm import (
    has_storm,
    storm_copy_count,
    supports_storm_copies,
)
from engine.abilities.keywords.casting.cast_adjustments import (
    CastAdjustmentInput,
    CastAdjustmentResult,
    resolve_cast_adjustments,
)
from engine.abilities.keywords.casting.convoke import (
    has_convoke,
    normalize_convoke_creature_ids,
    resolve_convoke_for_cast,
)
from engine.abilities.keywords.casting.bestow import (
    bestow_host_error,
    bestow_mana_needed,
    has_bestow,
    normalize_bestow,
)
from engine.abilities.keywords.casting.cast_mana import resolve_announce_cast_mana
from engine.abilities.keywords.casting.overload import (
    has_overload,
    normalize_overloaded,
    overload_creature_targets,
    overload_hits_each_creature,
    overload_mana_needed,
    overload_opponent_indices,
    resolve_overload_burn_damage,
)
from engine.abilities.keywords.casting.entwine import (
    cast_mana_with_entwine,
    entwine_cost,
    entwined_extra_draw,
    has_entwine,
    normalize_entwined,
    entwine_mana_needed,
    resolve_burn_damage,
)
from engine.abilities.keywords.casting.delve import (
    has_delve,
    normalize_delve_graveyard_indices,
    resolve_delve_for_cast,
)
from engine.abilities.keywords.casting.jump_start import (
    can_cast_via_jump_start,
    discard_for_jump_start,
    has_jump_start,
    jump_start_cost,
    jump_start_discard_error,
    jump_start_mana_needed,
)
from engine.abilities.keywords.casting.improvise import (
    has_improvise,
    normalize_improvise_artifact_ids,
    resolve_improvise_for_cast,
)
from engine.abilities.keywords.casting.kicker import (
    cast_mana_needed,
    extra_draw_from_kicker,
    has_kicker,
    is_multikicker,
    kicker_cost,
    kicker_mana_per_time,
    kicked_counter_count,
    normalize_kicker_times,
    pump_with_kicker,
    spell_damage,
)

__all__ = [
    'aftermath_mana_needed',
    'can_cast_aftermath',
    'can_cast_via_escape',
    'has_aftermath',
    'can_cast_via_flashback',
    'can_cast_via_jump_start',
    'discard_for_jump_start',
    'has_jump_start',
    'jump_start_cost',
    'jump_start_discard_error',
    'jump_start_mana_needed',
    'escape_cost',
    'escape_exiles_required',
    'escape_mana_needed',
    'escape_payment_error',
    'exile_for_escape_cost',
    'has_escape',
    'bestow_host_error',
    'bestow_mana_needed',
    'cast_mana_needed',
    'cast_mana_with_entwine',
    'has_bestow',
    'has_overload',
    'normalize_bestow',
    'normalize_overloaded',
    'overload_creature_targets',
    'overload_hits_each_creature',
    'overload_mana_needed',
    'overload_opponent_indices',
    'resolve_announce_cast_mana',
    'resolve_overload_burn_damage',
    'entwine_cost',
    'entwined_extra_draw',
    'entwine_mana_needed',
    'has_entwine',
    'normalize_entwined',
    'resolve_burn_damage',
    'CastAdjustmentInput',
    'CastAdjustmentResult',
    'has_convoke',
    'has_delve',
    'has_improvise',
    'normalize_convoke_creature_ids',
    'normalize_delve_graveyard_indices',
    'normalize_improvise_artifact_ids',
    'resolve_cast_adjustments',
    'resolve_convoke_for_cast',
    'resolve_delve_for_cast',
    'resolve_improvise_for_cast',
    'has_cascade',
    'extra_draw_from_kicker',
    'flashback_cost',
    'flashback_mana_needed',
    'has_flashback',
    'has_kicker',
    'is_multikicker',
    'kicker_cost',
    'kicker_mana_per_time',
    'kicked_counter_count',
    'normalize_kicker_times',
    'pump_with_kicker',
    'has_storm',
    'reveal_cascade_hit',
    'spell_damage',
    'spell_mana_value',
    'storm_copy_count',
    'supports_storm_copies',
]
