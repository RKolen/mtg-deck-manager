"""Cast-modifier keywords (one module per keyword as integration proceeds)."""

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
from engine.abilities.keywords.casting.delve import (
    has_delve,
    normalize_delve_graveyard_indices,
    resolve_delve_for_cast,
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
    'can_cast_via_flashback',
    'cast_mana_needed',
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
