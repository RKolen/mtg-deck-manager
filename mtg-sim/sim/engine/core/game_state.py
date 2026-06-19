"""
Central game state for the MTG rules engine.

GameState is a pure data container: it holds every mutable piece of game
information but contains no action logic. The game loop (engine/game.py,
Phase B) reads and writes it; the rules modules (stack, SBAs, combat, …)
receive it as a parameter.

PlayerInfo tracks per-player mutable state that is not tracked by ZoneManager
(life, poison, mana pool, land-played flag).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.core.game_object import CardObject, Permanent, Target
from engine.core.mana import ManaPool
from engine.core.turn_structure import TurnRunner
from engine.core.turn_structure import Step
from engine.core.zones import Zone, ZoneManager, ZoneMoveEvent
from engine.abilities.keywords import enters_ready, has_persist, has_undying
from engine.abilities.keywords.other.afterlife import apply_afterlife_on_die
from engine.abilities.keywords.other.ascend import update_ascend_status
from engine.abilities.keywords.other.champion import (
    has_champion,
    release_championed_creature,
)
from engine.abilities.keywords.other.extort import apply_extort_on_spell_cast
from engine.abilities.keywords.other.intensity import apply_intensity_on_spell_cast
from engine.abilities.keywords.other.haunt import (
    apply_haunt_on_creature_death,
    clear_haunt_on_leave_battlefield,
    has_haunt,
)
from engine.abilities.keywords.other.modular import apply_modular_on_die
from engine.rules.state_based import check_sbas
from engine.rules.stack import Stack
from engine.rules.triggers import AttackTriggerEvent, BlockTriggerEvent
from engine.rules.triggers import MassAttackTriggerEvent
from engine.rules.triggers import CombatDamageTriggerEvent
from engine.rules.triggers import LifeGainedTriggerEvent
from engine.rules.triggers import StepTriggerEvent, TriggerRegistry, spell_cast_event


@dataclass
class _PlayerVitals:
    """Life, mana, and land-drop state for one player."""

    life: int = 20
    poison: int = 0
    mana_pool: ManaPool = field(default_factory=ManaPool)
    land_played: bool = False


@dataclass
class _TurnFlags:
    """Per-turn boolean trackers for one player."""

    spells_cast: int = 0
    combat_damage_dealt: bool = False
    was_dealt_damage: bool = False
    revolt: bool = False
    permanents_entered: int = 0


@dataclass
class PlayerInfo:
    """Per-player state that lives outside the zone system."""

    name: str
    vitals: _PlayerVitals = field(default_factory=_PlayerVitals)
    turn_flags: _TurnFlags = field(default_factory=_TurnFlags)
    ascended: bool = False
    dungeon_room: int = 0
    attractions: int = 0
    has_lost: bool = False

    @property
    def life(self) -> int:
        """Current life total."""
        return self.vitals.life

    @life.setter
    def life(self, value: int) -> None:
        """Set current life total."""
        self.vitals.life = value

    @property
    def poison(self) -> int:
        """Current poison counter count."""
        return self.vitals.poison

    @poison.setter
    def poison(self, value: int) -> None:
        """Set poison counter count."""
        self.vitals.poison = value

    @property
    def mana_pool(self) -> ManaPool:
        """Floating mana available this step."""
        return self.vitals.mana_pool

    @mana_pool.setter
    def mana_pool(self, value: ManaPool) -> None:
        """Replace floating mana pool."""
        self.vitals.mana_pool = value

    @property
    def land_played(self) -> bool:
        """True when a land was played this turn."""
        return self.vitals.land_played

    @land_played.setter
    def land_played(self, value: bool) -> None:
        """Set whether a land was played this turn."""
        self.vitals.land_played = value

    @property
    def spells_cast_this_turn(self) -> int:
        """Number of spells cast this turn."""
        return self.turn_flags.spells_cast

    @spells_cast_this_turn.setter
    def spells_cast_this_turn(self, value: int) -> None:
        """Set spells cast this turn."""
        self.turn_flags.spells_cast = value

    @property
    def combat_damage_dealt_this_turn(self) -> bool:
        """True when combat damage was dealt this turn."""
        return self.turn_flags.combat_damage_dealt

    @combat_damage_dealt_this_turn.setter
    def combat_damage_dealt_this_turn(self, value: bool) -> None:
        """Set combat damage dealt flag."""
        self.turn_flags.combat_damage_dealt = value

    @property
    def was_dealt_damage_this_turn(self) -> bool:
        """True when this player was dealt damage this turn."""
        return self.turn_flags.was_dealt_damage

    @was_dealt_damage_this_turn.setter
    def was_dealt_damage_this_turn(self, value: bool) -> None:
        """Set was-dealt-damage flag."""
        self.turn_flags.was_dealt_damage = value

    @property
    def revolt_this_turn(self) -> bool:
        """True when a permanent left this player's battlefield this turn."""
        return self.turn_flags.revolt

    @revolt_this_turn.setter
    def revolt_this_turn(self, value: bool) -> None:
        """Set revolt flag."""
        self.turn_flags.revolt = value

    @property
    def permanents_entered_this_turn(self) -> int:
        """Number of permanents that entered the battlefield this turn."""
        return self.turn_flags.permanents_entered

    @permanents_entered_this_turn.setter
    def permanents_entered_this_turn(self, value: int) -> None:
        """Set permanents entered count."""
        self.turn_flags.permanents_entered = value


@dataclass
class LogEntry:
    """One timestamped line in the game log."""

    turn: int
    actor: str
    action: str
    detail: str = ""


@dataclass
class _DeathTurnFlags:
    """Per-turn death counters for gravestorm and morbid."""

    creature_died: bool = False
    permanents_died: int = 0


@dataclass
class _GameMeta:
    """Auxiliary game-level state for one session."""

    trigger_registry: TriggerRegistry = field(default_factory=TriggerRegistry)
    log: list[LogEntry] = field(default_factory=list)
    winner: int | None = None
    deaths: _DeathTurnFlags = field(default_factory=_DeathTurnFlags)


@dataclass
class GameState:
    """All mutable state for one game session.

    Modules that implement rules receive a GameState and may mutate it.
    The game loop in engine/game.py (Phase B) owns the game-id → GameState
    mapping and is the only caller of action methods.
    """

    game_id: str
    zones: ZoneManager
    players: list[PlayerInfo]
    turn: TurnRunner
    stack: Stack
    meta: _GameMeta = field(default_factory=_GameMeta)

    @property
    def trigger_registry(self) -> TriggerRegistry:
        """Trigger registry for this game session."""
        return self.meta.trigger_registry

    @property
    def log(self) -> list[LogEntry]:
        """Game event log."""
        return self.meta.log

    @property
    def winner(self) -> int | None:
        """Index of the winning player, or None if game is ongoing."""
        return self.meta.winner

    @winner.setter
    def winner(self, value: int | None) -> None:
        """Set the winning player index."""
        self.meta.winner = value

    @property
    def creature_died_this_turn(self) -> bool:
        """True when a creature died this turn."""
        return self.meta.deaths.creature_died

    @creature_died_this_turn.setter
    def creature_died_this_turn(self, value: bool) -> None:
        """Set creature-died flag."""
        self.meta.deaths.creature_died = value

    def __post_init__(self) -> None:
        """Subscribe the trigger registry to zone movement events."""
        self.zones.register_listener(self._handle_zone_move)

    @property
    def active_player_idx(self) -> int:
        """Index of the player whose turn it currently is."""
        return self.turn.active_player_idx

    @property
    def non_active_player_idx(self) -> int:
        """Index of the player whose turn it is NOT."""
        return 1 - self.active_player_idx

    def log_event(self, actor: str, action: str, detail: str = "") -> None:
        """Append one entry to the game log."""
        self.log.append(LogEntry(
            turn=self.turn.context.turn_number,
            actor=actor,
            action=action,
            detail=detail,
        ))

    def check_sbas(self) -> list:
        """Apply state-based actions and return the emitted SBA events."""
        return check_sbas(self)

    def try_keyword_death_replacement(self, perm: Permanent) -> bool:
        """Apply persist/undying instead of destroying a creature; return True if replaced."""
        if 'Creature' not in perm.type_line or perm.is_token:
            return False
        if has_persist(perm) and perm.counters.get('-1/-1', 0) == 0:
            perm.counters['-1/-1'] = 1
            perm.damage_marked = 0
            self.log_event('rules', 'persist', f'{perm.name} returned with -1/-1')
            return True
        if has_undying(perm) and perm.counters.get('+1/+1', 0) == 0:
            perm.counters['+1/+1'] = 1
            perm.damage_marked = 0
            perm.sick = not enters_ready(perm)
            self.log_event('rules', 'undying', f'{perm.name} returned with +1/+1')
            return True
        return False

    def _note_zone_move_flags(self, event: ZoneMoveEvent) -> None:
        """Track Morbid, Revolt, Celebration, and similar ability-word state."""
        if isinstance(event.obj, Permanent) and event.to_zone == Zone.BATTLEFIELD:
            self.players[event.player_idx].permanents_entered_this_turn += 1
            ascend_detail = update_ascend_status(self, event.player_idx)
            if ascend_detail:
                self.log_event('rules', 'ascend', ascend_detail)
        if not isinstance(event.obj, Permanent):
            return
        if event.from_zone == Zone.BATTLEFIELD:
            self.players[event.obj.controller_idx].revolt_this_turn = True
            clear_haunt_on_leave_battlefield(event.obj)
            if has_champion(event.obj):
                release_detail = release_championed_creature(self, event.obj)
                if release_detail:
                    self.log_event('rules', 'champion', release_detail)
        if (
            event.from_zone == Zone.BATTLEFIELD
            and event.to_zone == Zone.GRAVEYARD
        ):
            self.meta.deaths.permanents_died += 1
            modular_detail = apply_modular_on_die(self, event.obj)
            if modular_detail:
                self.log_event('rules', 'modular', modular_detail)
            afterlife_detail = apply_afterlife_on_die(self, event.obj)
            if afterlife_detail:
                self.log_event('rules', 'afterlife', afterlife_detail)
            if has_haunt(event.obj):
                haunt_detail = apply_haunt_on_creature_death(self, event.obj)
                if haunt_detail:
                    self.log_event('rules', 'haunt', haunt_detail)
            if 'Creature' in event.obj.type_line:
                self.creature_died_this_turn = True

    def _handle_zone_move(self, event: ZoneMoveEvent) -> None:
        """Put matching triggered abilities on the stack."""
        self._note_zone_move_flags(event)
        self.trigger_registry.put_triggers_on_stack(event, self)

    def fire_step_triggers(self, step: Step) -> None:
        """Put triggered abilities for the beginning of a step on the stack."""
        event = StepTriggerEvent(
            step=step,
            active_player_idx=self.active_player_idx,
        )
        self.trigger_registry.put_triggers_on_stack(event, self)

    def fire_attack_triggers(self, attacker: Permanent) -> None:
        """Put triggered abilities for a declared attacker on the stack."""
        event = AttackTriggerEvent(
            attacker_id=attacker.obj_id,
            attacking_player_idx=attacker.controller_idx,
        )
        self.trigger_registry.put_triggers_on_stack(event, self)

    def fire_mass_attack_triggers(
        self,
        attacking_player_idx: int,
        attacker_count: int,
    ) -> None:
        """Put Battalion-style triggers for declaring multiple attackers."""
        if attacker_count <= 0:
            return
        self.trigger_registry.put_triggers_on_stack(
            MassAttackTriggerEvent(
                attacking_player_idx=attacking_player_idx,
                attacker_count=attacker_count,
            ),
            self,
        )

    def fire_block_triggers(self, blocker: Permanent, attacker: Permanent) -> None:
        """Put triggered abilities for a declared blocker on the stack."""
        event = BlockTriggerEvent(
            blocker_id=blocker.obj_id,
            attacker_id=attacker.obj_id,
            defending_player_idx=blocker.controller_idx,
        )
        self.trigger_registry.put_triggers_on_stack(event, self)

    def fire_spell_cast_triggers(
        self,
        spell: CardObject,
        targets: tuple[Target, ...] = (),
    ) -> None:
        """Put triggered abilities for a cast spell on the stack."""
        self.trigger_registry.put_triggers_on_stack(
            spell_cast_event(spell, targets),
            self,
        )
        extort_detail = apply_extort_on_spell_cast(self, spell.controller_idx)
        if extort_detail:
            self.log_event('rules', 'extort', extort_detail)
        card_info = spell.card_info
        for detail in apply_intensity_on_spell_cast(self, spell.controller_idx, card_info):
            self.log_event('rules', 'intensity', detail)

    def mark_player_was_dealt_damage(self, player_idx: int) -> None:
        """Record that a player was dealt damage this turn (Raid and similar)."""
        self.players[player_idx].was_dealt_damage_this_turn = True

    def gain_life(
        self,
        player_idx: int,
        amount: int,
        source_permanent_id: int | None = None,
    ) -> None:
        """Gain life and put matching life-gain triggers on the stack."""
        if amount <= 0:
            return
        self.players[player_idx].life += amount
        self.trigger_registry.put_triggers_on_stack(
            LifeGainedTriggerEvent(
                player_idx=player_idx,
                amount=amount,
                source_permanent_id=source_permanent_id,
            ),
            self,
        )

    def fire_combat_damage_triggers(
        self,
        source: Permanent,
        amount: int,
        damaged_player_idx: int | None = None,
        damaged_permanent: Permanent | None = None,
    ) -> None:
        """Put triggered abilities for combat damage dealt by a permanent on the stack."""
        if amount <= 0:
            return
        self.trigger_registry.put_triggers_on_stack(
            CombatDamageTriggerEvent(
                source_permanent_id=source.obj_id,
                controller_idx=source.controller_idx,
                amount=amount,
                damaged_player_idx=damaged_player_idx,
                damaged_permanent_id=(
                    damaged_permanent.obj_id if damaged_permanent is not None else None
                ),
            ),
            self,
        )

    def to_client(self) -> dict:
        """Serialise public game state, hiding the opponent's hand contents."""
        return {
            "gameId": self.game_id,
            "turn": self.turn.context.turn_number,
            "turnState": self.turn.to_dict(),
            "phase": self.turn.current_step.value,
            "winner": self.winner,
            "player": self._player_to_client(0, reveal_hand=True),
            "opponent": self._player_to_client(1, reveal_hand=False),
            "battlefield": {
                "player": [p.to_dict() for p in self.zones.permanents_of(0)],
                "opponent": [p.to_dict() for p in self.zones.permanents_of(1)],
            },
            "stack": self.stack.to_client(),
            "log": [entry.__dict__ for entry in self.log],
        }

    def _player_to_client(self, player_idx: int, reveal_hand: bool) -> dict:
        """Serialise one player's public state."""
        zones = self.zones.player_zones[player_idx]
        player = self.players[player_idx]
        data = {
            "name": player.name,
            "life": player.life,
            "poison": player.poison,
            "manaPool": player.mana_pool.total(),
            "landPlayed": player.land_played,
            "graveyard": [_card_name(c) for c in zones.graveyard],
            "libraryCount": len(zones.library),
            "handCount": len(zones.hand),
        }
        if reveal_hand:
            data["hand"] = [_card_name(c) for c in zones.hand]
        return data


def _card_name(card: object) -> str:
    """Return a display name for a CardObject-like value."""
    card_info = getattr(card, "card_info", None)
    return getattr(card_info, "name", "")
