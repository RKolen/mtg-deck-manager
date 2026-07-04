# Rules edge cases (Phase E integration reference)

Documented interactions the simplified engine implements or approximates.
Each entry points at tests that lock the behaviour.

## Combat

### Deathtouch + trample

A deathtouch trampler must assign at least 1 damage to each blocking creature
before excess can be dealt to the defending player. First-strike variants apply
the same rule in the first-strike step.

- `tests/unit/test_combat.py::test_deathtouch_trample_assigns_one_to_blocker_then_excess`
- `tests/unit/test_combat.py::test_first_strike_deathtouch_trample_excess_hits_before_return_damage`

### Menace

Menace requires two or more blockers; a single blocker is illegal.

- `tests/unit/test_combat.py` (menace blocker tests)

## Counter / death replacement keywords

### Persist + undying on the same creature

Persist returns a creature with a −1/−1 counter when it dies without one;
undying returns it with a +1/+1 counter when it dies without one. The engine
applies these as separate leave-battlefield replacements (simplified ordering).

- `tests/unit/test_keywords_ext.py::test_persist_returns_creature_without_minus_counter`
- `tests/unit/test_keywords_ext.py::test_undying_returns_creature_without_plus_counter`

### Modular on death

When a modular artifact creature dies, its +1/+1 counters move to another
artifact you control.

- `tests/unit/test_keywords_other_batch34.py::test_modular_moves_counters_to_another_artifact_on_die`

### Afterlife

When a creature with afterlife dies, Spirit tokens are created.

- `tests/integration/test_keywords_game_ability_other.py::test_afterlife_creates_spirits_when_creature_dies`

## Casting and alternate costs

### Storm + cascade

Storm copies count spells cast this turn before the storm spell resolves.
Cascade reveals and may cast a cheaper spell for free. Both are wired through
the casting pipeline; combined ordering is stack-based (simplified).

- `tests/integration/test_keywords_game.py::test_storm_spell_creates_and_resolves_copies`
- `tests/integration/test_keywords_game.py::test_cascade_casts_free_spell_from_library`

### Convoke, delve, improvise

Mana reductions stack in order: delve exiles graveyard cards, convoke taps
creatures, improvise taps artifacts.

- `tests/integration/test_keywords_game_ability_other.py::test_convoke_cast_taps_creatures_to_reduce_mana`
- `tests/integration/test_keywords_game.py::test_delve_cast_exiles_graveyard_to_pay_mana`
- `tests/integration/test_keywords_game.py::test_improvise_cast_taps_artifacts_to_pay_mana`

### Evoke

Casting for evoke marks the permanent; it sacrifices on ETB instead of staying.

- `tests/integration/test_keywords_game_ability_other.py::test_evoke_cast_sacrifices_creature_on_resolve`

### Affinity

Affinity for artifacts reduces generic mana by the number of artifacts you control.

- `tests/integration/test_keywords_game_ability_other.py::test_affinity_creature_casts_with_one_fewer_land`

## ETB / ability_other

### Exploit

On ETB, exploit sacrifices the controller's lowest-power other creature.

- `tests/integration/test_keywords_game_ability_other.py::test_exploit_sacrifices_creature_on_etb_in_game_loop`

### Evolve

When a larger creature enters under your control, evolve sources get +1/+1.

- `tests/integration/test_keywords_game_ability_other.py::test_evolve_puts_counter_when_larger_creature_enters`

### Fabricate

Fabricate ETB adds +1/+1 counters or Servo tokens depending on oracle text.

- `tests/integration/test_keywords_game_ability_other.py::test_fabricate_creature_enters_with_counters`

### Extort

Extort drains each opponent when you cast a spell.

- `tests/integration/test_keywords_game_ability_other.py::test_extort_drains_when_spell_is_cast`

### Renown

Renown marks the creature and adds +1/+1 after it deals combat damage to a player.

- `tests/integration/test_keywords_game_ability_other.py::test_renown_marks_creature_after_unblocked_damage`

### Morph / disguise

Face-down cast uses morph or disguise alternate costs; turn-up is a separate activated path.

- `tests/integration/test_keywords_game_ability_other.py::test_morph_cast_enters_face_down`
- `tests/integration/test_keywords_game_ability_other.py::test_disguise_cast_enters_face_down`

### Living weapon

Equipment with living weapon creates a Germ token and attaches to it.

- `tests/integration/test_keywords_game.py::test_living_weapon_creates_germ_on_cast`

## Replacement effects (Phase F overlap)

### Regeneration shield

Regeneration replaces destruction from lethal damage; the creature stays with
damage cleared.

- `tests/unit/test_replacement.py::test_regeneration_shield_survives_lethal_damage`

### Leyline of the Void

Cards that would enter a graveyard are exiled instead (controller-scoped simplification).

- `tests/unit/test_replacement.py::test_leyline_of_void_sends_destroyed_creature_to_exile`
- `tests/unit/test_replacement.py::test_mill_with_leyline_sends_to_exile`

## Continuous effects (Phase F overlap)

### Humility

Humility strips creature abilities and sets base P/T to 1/1 (layers 6 + 7b).

- `tests/unit/test_continuous.py::test_humility_makes_creatures_one_one_without_abilities`
- `tests/unit/test_continuous.py::test_humility_strips_hexproof_for_targeting`
