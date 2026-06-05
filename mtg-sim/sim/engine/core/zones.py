"""
Zone system for the MTG rules engine.

All zone transitions go through ZoneManager so that:
  - Trigger listeners are notified of every object movement.
  - Token-cessation rules are enforced automatically (CR 111.7).
  - Object identity is preserved across zone changes (CR 400.7).

Callers must never mutate the underlying lists directly; always use the
ZoneManager methods so the listener chain fires correctly.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from engine.core.game_object import (
    CardObject,
    EmblemObject,
    Permanent,
    SpellOnStack,
    StackObject,
    TokenObject,
    ZoneCard,
    _PermanentState,
)

if TYPE_CHECKING:
    from engine.core.game_state import GameState


class Zone(enum.Enum):
    """All zones defined by the MTG Comprehensive Rules (CR 400.1)."""

    LIBRARY = "library"
    HAND = "hand"
    BATTLEFIELD = "battlefield"
    GRAVEYARD = "graveyard"
    EXILE = "exile"
    STACK = "stack"
    COMMAND = "command"


@dataclass
class ZoneMoveEvent:
    """Emitted by ZoneManager whenever an object changes zones.

    Trigger listeners subscribe via ZoneManager.register_listener and
    receive one ZoneMoveEvent per object movement.
    """

    obj: Permanent | CardObject | TokenObject | StackObject | EmblemObject
    from_zone: Zone | None
    to_zone: Zone
    cause: str
    player_idx: int


ZoneMoveListener = Callable[[ZoneMoveEvent], None]


@dataclass
class PlayerZones:
    """The four private zones belonging to one player."""

    library: list[ZoneCard] = field(default_factory=list)
    hand: list[ZoneCard] = field(default_factory=list)
    graveyard: list[ZoneCard] = field(default_factory=list)
    exile: list[ZoneCard] = field(default_factory=list)


@dataclass
class ZoneManager:
    """Central authority for all zone transitions.

    The battlefield and stack are shared between both players. Each player's
    library, hand, graveyard, and exile are in player_zones[player_idx].
    """

    player_zones: list[PlayerZones] = field(
        default_factory=lambda: [PlayerZones(), PlayerZones()]
    )
    battlefield: list[Permanent] = field(default_factory=list)
    stack: list[StackObject] = field(default_factory=list)
    command: list[EmblemObject] = field(default_factory=list)
    _listeners: list[ZoneMoveListener] = field(default_factory=list, repr=False)

    def register_listener(self, listener: ZoneMoveListener) -> None:
        """Subscribe to all future zone-move events."""
        self._listeners.append(listener)

    # ------------------------------------------------------------------
    # Entering the battlefield
    # ------------------------------------------------------------------

    def enter_battlefield(
        self,
        source: CardObject | TokenObject,
        controller_idx: int,
        cause: str,
        from_zone: Zone | None = None,
    ) -> Permanent:
        """Create a new Permanent on the battlefield for the given source.

        If from_zone is provided, the source is removed from that zone first.
        A new Permanent is always created (new game object, new obj_id) to
        reflect the zone-change new-object rule (CR 400.7).
        """
        if from_zone is not None and isinstance(source, CardObject):
            self._remove_from_player_zone(source, from_zone, source.owner_idx)

        perm = Permanent(
            controller_idx=controller_idx,
            owner_idx=source.owner_idx,
            source=source,
            state=_PermanentState(sick=True),
        )
        if "Creature" in perm.type_line and "haste" in perm.oracle_text.lower():
            perm.sick = False
        self.battlefield.append(perm)
        self._emit(ZoneMoveEvent(
            obj=perm,
            from_zone=from_zone,
            to_zone=Zone.BATTLEFIELD,
            cause=cause,
            player_idx=controller_idx,
        ))
        return perm

    # ------------------------------------------------------------------
    # Leaving the battlefield
    # ------------------------------------------------------------------

    def leave_battlefield(
        self,
        perm: Permanent,
        to_zone: Zone,
        cause: str,
        game: GameState | None = None,
    ) -> None:
        """Remove a permanent from the battlefield and route its source card.

        Tokens cease to exist rather than entering any other zone (CR 111.7).
        Non-token cards are placed in to_zone under their owner's control.
        When game is provided, persist/undying may prevent destruction.
        """
        if perm not in self.battlefield:
            return

        if (
            game is not None
            and to_zone == Zone.GRAVEYARD
            and game.try_keyword_death_replacement(perm)
        ):
            return

        self.battlefield.remove(perm)
        self._emit(ZoneMoveEvent(
            obj=perm,
            from_zone=Zone.BATTLEFIELD,
            to_zone=to_zone,
            cause=cause,
            player_idx=perm.owner_idx,
        ))

        if perm.is_token:
            return

        assert isinstance(perm.source, CardObject)
        self._place_card_in_zone(perm.source, to_zone, perm.owner_idx)

    # ------------------------------------------------------------------
    # Library and hand operations
    # ------------------------------------------------------------------

    def draw(self, player_idx: int) -> CardObject | None:
        """Draw the top card of a player's library into their hand.

        Returns the drawn CardObject, or None if the library is empty
        (the engine must handle the draw-from-empty-library loss condition
        via state-based actions in Phase E5).
        """
        lib = self.player_zones[player_idx].library
        if not lib:
            return None
        card = lib.pop(0)
        self.player_zones[player_idx].hand.append(card)
        self._emit(ZoneMoveEvent(
            obj=card,
            from_zone=Zone.LIBRARY,
            to_zone=Zone.HAND,
            cause="draw",
            player_idx=player_idx,
        ))
        if isinstance(card, CardObject):
            return card
        return None

    def play_from_hand(self, card: CardObject, player_idx: int) -> None:
        """Remove a card from hand when it is cast or played as a land."""
        hand = self.player_zones[player_idx].hand
        if card in hand:
            hand.remove(card)

    def cast_from_graveyard(self, card: CardObject, player_idx: int) -> None:
        """Remove a card from graveyard when it is cast via flashback."""
        graveyard = self.player_zones[player_idx].graveyard
        if card in graveyard:
            graveyard.remove(card)
            self._emit(ZoneMoveEvent(
                obj=card,
                from_zone=Zone.GRAVEYARD,
                to_zone=Zone.STACK,
                cause="flashback",
                player_idx=player_idx,
            ))

    def move_graveyard_to_hand(self, card: CardObject, owner_idx: int) -> None:
        """Return a card from graveyard to its owner's hand."""
        gy = self.player_zones[owner_idx].graveyard
        if card in gy:
            gy.remove(card)
            self.player_zones[owner_idx].hand.append(card)
            self._emit(ZoneMoveEvent(
                obj=card,
                from_zone=Zone.GRAVEYARD,
                to_zone=Zone.HAND,
                cause="return",
                player_idx=owner_idx,
            ))

    def exile_from_graveyard(self, card: CardObject, owner_idx: int) -> None:
        """Move a card from graveyard to exile."""
        gy = self.player_zones[owner_idx].graveyard
        if card in gy:
            gy.remove(card)
            self.player_zones[owner_idx].exile.append(card)
            self._emit(ZoneMoveEvent(
                obj=card,
                from_zone=Zone.GRAVEYARD,
                to_zone=Zone.EXILE,
                cause="exile",
                player_idx=owner_idx,
            ))

    # ------------------------------------------------------------------
    # Stack operations
    # ------------------------------------------------------------------

    def push_stack(self, obj: StackObject) -> None:
        """Place a spell or ability on top of the stack."""
        self.stack.append(obj)
        cause = "cast" if isinstance(obj, SpellOnStack) else "ability"
        self._emit(ZoneMoveEvent(
            obj=obj,
            from_zone=None,
            to_zone=Zone.STACK,
            cause=cause,
            player_idx=obj.controller_idx,
        ))

    def pop_stack(self) -> StackObject | None:
        """Pop the top stack object for resolution. Returns None if empty."""
        return self.stack.pop() if self.stack else None

    # ------------------------------------------------------------------
    # Command zone
    # ------------------------------------------------------------------

    def add_emblem(self, emblem: EmblemObject) -> None:
        """Place an emblem in the command zone."""
        self.command.append(emblem)
        self._emit(ZoneMoveEvent(
            obj=emblem,
            from_zone=None,
            to_zone=Zone.COMMAND,
            cause="created",
            player_idx=emblem.controller_idx,
        ))

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def permanents_of(self, controller_idx: int) -> list[Permanent]:
        """All permanents controlled by one player."""
        return [p for p in self.battlefield if p.controller_idx == controller_idx]

    def creatures_of(self, controller_idx: int) -> list[Permanent]:
        """All creature permanents controlled by one player."""
        return [p for p in self.permanents_of(controller_idx) if _is_creature(p)]

    def lands_of(self, controller_idx: int) -> list[Permanent]:
        """All land permanents controlled by one player."""
        return [p for p in self.permanents_of(controller_idx) if _is_land(p)]

    def untapped_lands_of(self, controller_idx: int) -> list[Permanent]:
        """All untapped land permanents controlled by one player."""
        return [p for p in self.lands_of(controller_idx) if not p.tapped]

    def find_permanent(self, obj_id: int) -> Permanent | None:
        """Return the battlefield permanent with the given obj_id, or None."""
        return next((p for p in self.battlefield if p.obj_id == obj_id), None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _place_card_in_zone(
        self, card: CardObject, zone: Zone, player_idx: int
    ) -> None:
        pz = self.player_zones[player_idx]
        destination: dict[Zone, list[ZoneCard]] = {
            Zone.GRAVEYARD: pz.graveyard,
            Zone.HAND: pz.hand,
            Zone.EXILE: pz.exile,
            Zone.LIBRARY: pz.library,
        }
        target = destination.get(zone)
        if target is not None:
            target.append(card)

    def _remove_from_player_zone(
        self, card: CardObject, zone: Zone, player_idx: int
    ) -> None:
        pz = self.player_zones[player_idx]
        source: dict[Zone, list[ZoneCard]] = {
            Zone.HAND: pz.hand,
            Zone.LIBRARY: pz.library,
            Zone.GRAVEYARD: pz.graveyard,
            Zone.EXILE: pz.exile,
        }
        origin = source.get(zone)
        if origin is not None and card in origin:
            origin.remove(card)

    def _emit(
        self, event: ZoneMoveEvent
    ) -> None:
        for listener in self._listeners:
            listener(event)


# ---------------------------------------------------------------------------
# Type helpers — kept module-level to avoid repeating the type-line logic
# ---------------------------------------------------------------------------

def _is_creature(perm: Permanent) -> bool:
    if isinstance(perm.source, TokenObject):
        return "Creature" in perm.source.type_line
    return bool(perm.card_info and "Creature" in perm.card_info.type_line)


def _is_land(perm: Permanent) -> bool:
    if isinstance(perm.source, TokenObject):
        return "Land" in perm.source.type_line
    return bool(perm.card_info and "Land" in perm.card_info.type_line)
