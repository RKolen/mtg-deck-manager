"""
The stack for the MTG rules engine (CR 405).

The stack is a LIFO queue of spells and abilities waiting to resolve.
Both players must pass priority consecutively with the stack non-empty
before the top object resolves.

Fizzle rule (CR 608.2b): if a spell or ability has targets and all of
them are illegal at the time it would resolve, it has no effect. Spell
cards go to their owner's graveyard; ability objects simply cease to exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.core.game_object import (
    CardObject,
    SpellOnStack,
    StackObject,
    Target,
)
from engine.core.zones import ZoneManager


@dataclass
class StackResolution:
    """Result returned by Stack.resolve_top.

    If fizzled is True the effect must not be applied; reason explains why.
    If fizzled is False the caller should apply obj.effect to the game state.
    obj is None only when the stack was empty when resolve_top was called.
    """

    obj: StackObject | None
    fizzled: bool
    reason: str


@dataclass
class Stack:
    """LIFO queue of spells and abilities (CR 405.1).

    The top of the stack is the last element in the list; push appends,
    pop removes from the end.
    """

    objects: list[StackObject] = field(default_factory=list)

    def push(self, obj: StackObject) -> None:
        """Place a spell or ability on top of the stack."""
        self.objects.append(obj)

    @property
    def top(self) -> StackObject | None:
        """Peek at the top stack object without removing it."""
        return self.objects[-1] if self.objects else None

    @property
    def is_empty(self) -> bool:
        """True when no spells or abilities are waiting to resolve."""
        return not self.objects

    def resolve_top(self, zones: ZoneManager) -> StackResolution:
        """Pop the top object; check targets; return a StackResolution.

        The caller is responsible for applying obj.effect when fizzled is False.
        Target legality in Phase A: a permanent target is legal if its obj_id
        still appears on the battlefield; a player target is always legal.
        Full legality (hexproof, shroud, protection) is added in Phase E.
        """
        if not self.objects:
            return StackResolution(obj=None, fizzled=True, reason="stack_empty")

        obj = self.objects.pop()

        if _has_targets(obj) and _all_targets_illegal(obj, zones):
            _move_spell_card_to_graveyard(obj, zones)
            return StackResolution(obj=obj, fizzled=True, reason="all_targets_illegal")

        return StackResolution(obj=obj, fizzled=False, reason="resolved")

    def counter_top(self, zones: ZoneManager) -> StackObject | None:
        """Remove the top object without resolving it (e.g. Counterspell).

        Spell cards go to graveyard; ability objects cease to exist.
        Returns the countered object, or None if the stack was empty.
        """
        if not self.objects:
            return None
        obj = self.objects.pop()
        _move_spell_card_to_graveyard(obj, zones)
        return obj

    def to_client(self) -> list[dict]:
        """Serialise the stack for the frontend (top first)."""
        result = []
        for obj in reversed(self.objects):
            entry: dict = {
                "type": type(obj).__name__,
                "controller": obj.controller_idx,
                "targets": [{"objId": t.obj_id, "playerIdx": t.player_idx}
                            for t in _get_targets(obj)],
            }
            if isinstance(obj, SpellOnStack) and obj.source:
                entry["name"] = obj.source.card_info.name if obj.source.card_info else "?"
            result.append(entry)
        return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_targets(obj: StackObject) -> list[Target]:
    """Return the target list for any stack object type."""
    return getattr(obj, "targets", [])


def _has_targets(obj: StackObject) -> bool:
    """True when the object has at least one declared target."""
    return bool(_get_targets(obj))


def _target_is_legal(target: Target, zones: ZoneManager) -> bool:
    """True when a target is still in a legal state for resolution.

    Phase A legality: player targets always legal; permanent targets legal
    if their obj_id is still on the battlefield.
    """
    if target.player_idx is not None:
        return True
    if target.obj_id is not None:
        return zones.find_permanent(target.obj_id) is not None
    return False


def _all_targets_illegal(obj: StackObject, zones: ZoneManager) -> bool:
    """True when every declared target is illegal (triggers fizzle)."""
    targets = _get_targets(obj)
    return bool(targets) and all(not _target_is_legal(t, zones) for t in targets)


def _move_spell_card_to_graveyard(obj: StackObject, zones: ZoneManager) -> None:
    """Place the source card of a spell in its owner's graveyard after fizzle/counter.

    Ability objects have no card to move; they simply cease to exist.
    """
    if not isinstance(obj, SpellOnStack):
        return
    source: CardObject | None = obj.source
    if source is None:
        return
    zones.player_zones[obj.owner_idx].graveyard.append(source)
