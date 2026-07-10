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

- `tests/integration/test_keywords_game_ability_other.py::test_modular_moves_counters_when_creature_dies`
- `tests/unit/test_keywords_other_batch.py::test_modular_transfers_counters_on_death`

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
- `tests/integration/test_keywords_game_ability_other.py::test_fabricate_servos_enters_when_oracle_requests_artifact_token`

### Prowl

Prowl marks the creature unblockable when a creature with a shared subtype
is in your graveyard as it enters.

- `tests/integration/test_keywords_game_ability_other.py::test_prowl_marks_unblockable_when_graveyard_matches_on_cast`

### Decayed

Decayed creatures cannot attack and are sacrificed at end of turn.

- `tests/integration/test_keywords_game_ability_other.py::test_decayed_creature_sacrificed_at_end_of_turn`

### Encore

Encore exiles a creature card from the graveyard and creates attacking token
copies for each opponent.

- `tests/integration/test_keywords_game_ability_other.py::test_encore_from_graveyard_creates_token_copy`

### Soulbond

Soulbond pairs two unpaired soulbond creatures you control on ETB.

- `tests/integration/test_keywords_game_ability_other.py::test_soulbond_pairs_creatures_on_second_cast`

### Offspring

Offspring creates a token copy when the creature enters.

- `tests/integration/test_keywords_game_ability_other.py::test_offspring_creates_token_on_cast`

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
Equipment pump text (`Equipped creature gets +X/+X`) is applied as counters so
the Germ survives state-based actions.

- `tests/integration/test_keywords_game_ability_other.py::test_living_weapon_cast_creates_germ_host`
- `tests/integration/test_keywords_game.py::test_living_weapon_creates_germ_on_cast`

### Bloodthirst

Bloodthirst adds +1/+1 counters on ETB when an opponent was dealt damage
this turn.

- `tests/integration/test_keywords_game_ability_other.py::test_bloodthirst_puts_counters_after_opponent_was_damaged`

### Riot

Riot adds a +1/+1 counter on ETB (simplified: always counter).

- `tests/integration/test_keywords_game_ability_other.py::test_riot_creature_enters_with_counter_in_game_loop`

### Devour

Devour sacrifices other creatures you control on ETB for +1/+1 counters.

- `tests/integration/test_keywords_game_ability_other.py::test_devour_sacrifices_creatures_on_cast`

### Graft

Graft moves one +1/+1 counter from another creature you control on ETB.

- `tests/integration/test_keywords_game_ability_other.py::test_graft_moves_counter_from_donor_on_cast`

### Backup

Backup puts +1/+1 counters on another creature you control on ETB.

- `tests/integration/test_keywords_game_ability_other.py::test_backup_puts_counters_on_ally_in_game_loop`

### Unleash

Unleash adds +1/+1 and marks the creature unable to block (simplified).

- `tests/integration/test_keywords_game_ability_other.py::test_unleash_creature_enters_with_counter_in_game_loop`

### Ascend

Ascend grants City's Blessing when you control ten permanents as the
ascend permanent enters.

- `tests/integration/test_keywords_game_ability_other.py::test_ascend_grants_citys_blessing_at_ten_permanents`

### Dash / blitz

Dashed creatures return to hand at end of turn; blitzed creatures are
sacrificed at end of turn.

- `tests/integration/test_keywords_game_ability_other.py::test_dash_creature_returns_to_hand_at_end_of_turn`
- `tests/integration/test_keywords_game_ability_other.py::test_blitz_creature_sacrificed_at_end_of_turn`

### Cipher

Cipher triggers when you cast an instant or sorcery spell (simplified log).

- `tests/integration/test_keywords_game_ability_other.py::test_cipher_triggers_when_instant_cast_in_game_loop`

### Persist / undying

Persist and undying replace destruction with a counter and cleared damage.

- `tests/integration/test_keywords_game_ability_other.py::test_undying_creature_survives_destruction_in_game_loop`
- `tests/integration/test_keywords_game_ability_other.py::test_persist_creature_survives_with_minus_counter_in_game_loop`
- `tests/unit/test_keywords_ext.py::test_persist_returns_creature_without_minus_counter`
- `tests/unit/test_keywords_ext.py::test_undying_returns_creature_without_plus_counter`

## Combat keywords (ability_other)

### Mentor / training

Mentor buffs a weaker attacking creature; training buffs this creature when a
stronger ally attacks with it.

- `tests/integration/test_keywords_game_ability_other.py::test_mentor_buffs_smaller_attacker_in_combat`
- `tests/integration/test_keywords_game_ability_other.py::test_training_puts_counter_when_stronger_ally_attacks`

### Exalted

Exalted grants +1/+1 when this creature attacks alone.

- `tests/integration/test_keywords_game_ability_other.py::test_exalted_solo_attack_adds_counter`

### Annihilator

Annihilator destroys defending permanents when this creature attacks.

- `tests/integration/test_keywords_game_ability_other.py::test_annihilator_destroys_defender_permanents_on_attack`

### Afflict

Afflict makes the defending player lose 1 life when this creature attacks.

- `tests/integration/test_keywords_game_ability_other.py::test_afflict_drains_defender_on_attack`

### Enlist

Enlist taps a non-attacking creature when this creature attacks.

- `tests/integration/test_keywords_game.py::test_enlist_taps_helper_and_draws`

## Combat keywords (ability_other, on-attack / damage)

### Bushido

Bushido adds +1/+1 when the creature blocks or becomes blocked.

- `tests/integration/test_keywords_game_combat_other.py::test_bushido_puts_counter_when_creature_blocks`

### Toxic / ingest

Toxic adds poison counters; ingest exiles the top card of the damaged library.

- `tests/integration/test_keywords_game_combat_other.py::test_toxic_adds_poison_on_unblocked_attack`
- `tests/integration/test_keywords_game_combat_other.py::test_ingest_exiles_library_card_on_attack`

### Battle cry / melee / dethrone

Battle cry buffs allies; melee rewards wide attacks; dethrone can draw when
damaging the player with the most life.

- `tests/integration/test_keywords_game_combat_other.py::test_battle_cry_buffs_other_attackers`
- `tests/integration/test_keywords_game_combat_other.py::test_melee_draws_with_three_attackers`
- `tests/integration/test_keywords_game_combat_other.py::test_dethrone_draws_when_attacking_highest_life_player`

### Sunburst / echo

Sunburst uses colored mana in the pool on ETB; echo marks upkeep payment owed.

- `tests/integration/test_keywords_game_combat_other.py::test_sunburst_puts_counters_from_mana_pool_on_cast`
- `tests/integration/test_keywords_game_combat_other.py::test_echo_marks_creature_on_cast`

## Phase E integration gate

Minimum automated bar before Phase G scripting expands (`test_e_integration_gate.py`).

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

## Phase F integration gate

Minimum automated bar for layers and replacement hooks (`test_f_integration_gate.py`).

### Absorb

Absorb reduces all damage to the permanent (combat and spells) via the damage
replacement queue.

- `tests/integration/test_phase_f_integration.py::test_absorb_reduces_shock_damage_in_game_loop`
- `tests/integration/test_phase_f_integration.py::test_absorb_reduces_combat_damage_when_blocking`
- `tests/unit/test_keywords_other_batch34.py::test_absorb_reduces_incoming_combat_damage`

### Hexproof from

Opponents cannot target with sources matching the stated quality (e.g. instants).

- `tests/integration/test_phase_f_integration.py::test_hexproof_from_instants_blocks_opponent_shock`
- `tests/unit/test_keywords_other_batch33.py::test_hexproof_from_blocks_creature_targeting`

### Living metal

Artifacts animate as 3/3 creatures during the player's combat phase.

- `tests/integration/test_phase_f_integration.py::test_living_metal_artifact_attacks_for_three_damage`
- `tests/unit/test_keywords_other_batch26.py::test_living_metal_animates_artifact_for_combat`

### Umbra armor

An umbra armor aura is exiled instead of the enchanted creature dying to damage.

- `tests/integration/test_phase_f_integration.py::test_umbra_armor_saves_creature_from_lethal_shock`
- `tests/unit/test_keywords_other_batch29.py::test_umbra_armor_saves_enchanted_creature`

### Rest in Peace

Cards that would enter a graveyard are exiled instead.

- `tests/integration/test_phase_f_integration.py::test_rest_in_peace_exiles_creature_destroyed_by_shock`
- `tests/unit/test_replacement.py::test_leyline_of_void_sends_destroyed_creature_to_exile`

### Regeneration shield

Regeneration replaces destruction from lethal damage; damage is cleared.

- `tests/integration/test_phase_f_integration.py::test_regeneration_shield_survives_lethal_shock`
- `tests/unit/test_replacement.py::test_regeneration_shield_survives_lethal_damage`

### Humility (layers 6 + 7b)

Humility strips abilities and sets base P/T to 1/1, enabling targeting and removal.

- `tests/integration/test_phase_f_integration.py::test_humility_allows_shock_to_target_hexproof_creature`
- `tests/unit/test_continuous.py::test_humility_makes_creatures_one_one_without_abilities`
