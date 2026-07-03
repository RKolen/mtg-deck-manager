"""Replacement effects (CR 614) — Phase E10."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from engine.rules.continuous import has_creature_keyword

if TYPE_CHECKING:
    from engine.core.game_object import Permanent
    from engine.core.game_state import GameState

_SHIELD_COUNTER = 'shield'
_REGENERATION_SHIELD = 'regeneration shield'
_LEYLINE_ORACLE = 'if a card would be put into an opponent'


@dataclass(frozen=True)
class DamageEvent:
    """Damage that would be dealt to a permanent."""

    receiver_id: int
    source_id: int | None
    amount: int


@dataclass
class _ReplacementCandidate:
    handler: Callable[[GameState, object], object | None]
    self_replacement: bool
    source_obj_id: int = 0


@dataclass
class ReplacementQueue:
    """Single-event replacement queue with CR 614.5 self-replacement priority."""

    _candidates: list[_ReplacementCandidate] = field(default_factory=list)

    def register(
        self,
        handler: Callable[[GameState, object], object | None],
        *,
        self_replacement: bool = False,
        source_obj_id: int = 0,
    ) -> None:
        """Add a handler; self-replacements are applied before other effects."""
        self._candidates.append(_ReplacementCandidate(
            handler=handler,
            self_replacement=self_replacement,
            source_obj_id=source_obj_id,
        ))

    def apply(self, game: GameState, event: object) -> object:
        """Apply replacements until the event stabilizes or is fully replaced."""
        current = event
        while True:
            progressed = False
            for self_only in (True, False):
                for candidate in self._candidates:
                    if candidate.self_replacement != self_only:
                        continue
                    updated = candidate.handler(game, current)
                    if updated is not None and updated != current:
                        current = updated
                        progressed = True
                        break
                if progressed:
                    break
            if not progressed:
                return current


def grant_regeneration_shield(perm: Permanent) -> None:
    """Mark a permanent with a regeneration shield (simplified regenerate)."""
    perm.counters[_REGENERATION_SHIELD] = 1


def consume_regeneration_shield(perm: Permanent) -> bool:
    """Consume shield if present; return True when destruction is prevented."""
    if perm.counters.get(_REGENERATION_SHIELD, 0) <= 0:
        return False
    perm.counters[_REGENERATION_SHIELD] = 0
    perm.damage_marked = 0
    return True


def apply_damage_with_replacements(
    game: GameState | None,
    receiver: Permanent,
    source: Permanent | None,
    amount: int,
) -> int:
    """Return damage actually marked after shield-counter replacement."""
    if amount <= 0:
        return 0
    if game is None:
        return amount
    event = DamageEvent(receiver.obj_id, source.obj_id if source else None, amount)
    queue = _damage_replacement_queue(receiver)
    result = queue.apply(game, event)
    if not isinstance(result, DamageEvent):
        return 0
    return result.amount


def try_prevent_creature_destruction(game: GameState, perm: Permanent) -> bool:
    """Return True when destroy is replaced (indestructible, regen, shield)."""
    if has_creature_keyword(game, perm, 'Indestructible'):
        return True
    if consume_regeneration_shield(perm):
        return True
    if perm.counters.get(_SHIELD_COUNTER, 0) > 0:
        perm.counters[_SHIELD_COUNTER] -= 1
        perm.damage_marked = 0
        return True
    return False


def leyline_of_void_active(game: GameState) -> bool:
    """Return True when Leyline of the Void is on the battlefield."""
    return any(_is_leyline_of_void(perm) for perm in game.zones.battlefield)


def _damage_replacement_queue(receiver: Permanent) -> ReplacementQueue:
    queue = ReplacementQueue()

    def shield_handler(
        _game: GameState,
        event: object,
    ) -> DamageEvent | None:
        if not isinstance(event, DamageEvent):
            return None
        if event.receiver_id != receiver.obj_id:
            return None
        if receiver.counters.get(_SHIELD_COUNTER, 0) <= 0:
            return None
        receiver.counters[_SHIELD_COUNTER] -= 1
        return DamageEvent(event.receiver_id, event.source_id, 0)

    queue.register(shield_handler, self_replacement=True, source_obj_id=receiver.obj_id)
    return queue


def _is_leyline_of_void(perm: Permanent) -> bool:
    return (
        perm.name == 'Leyline of the Void'
        or _LEYLINE_ORACLE in perm.oracle_text.lower()
    )
