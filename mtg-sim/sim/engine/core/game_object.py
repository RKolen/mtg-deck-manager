"""
Core game object hierarchy for the MTG rules engine.

Every object that exists in the game descends from GameObject. Each instance
receives a unique obj_id at creation, which persists across zone changes so
that effects can track objects across the game (CR 400.7). The timestamp is
set at creation time and used by the layer system to order simultaneous
continuous effects (CR 613.7).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from deck_registry import CardInfo
    from engine.core.game_state import GameState

_obj_counter: itertools.count[int] = itertools.count(1)
_ts_counter: itertools.count[int] = itertools.count(1)


def _next_id() -> int:
    return next(_obj_counter)


def _next_ts() -> int:
    return next(_ts_counter)


@dataclass
class GameObject:
    """Base class for all objects that exist in the game (CR 109)."""

    obj_id: int = field(default_factory=_next_id)
    timestamp: int = field(default_factory=_next_ts)
    controller_idx: int = 0
    owner_idx: int = 0


@dataclass
class CardObject(GameObject):
    """A physical card originating from a player's deck.

    The card_info reference is the static Scryfall/Drupal data. Multiple
    CardObject instances may share the same card_info (e.g. four copies of
    Lightning Bolt each get their own CardObject but the same CardInfo).
    """

    card_info: CardInfo | None = None


@dataclass
class TokenObject(GameObject):
    """A token created by a spell or ability effect.

    Tokens cease to exist in any zone other than the battlefield (CR 111.7),
    enforced by ZoneManager.leave_battlefield.
    """

    name: str = ""
    type_line: str = ""
    colors: list[str] = field(default_factory=list)
    power: str = "0"
    toughness: str = "0"
    oracle_text: str = ""
    created_by_obj_id: int = 0


@dataclass
class EmblemObject(GameObject):
    """An emblem created by a planeswalker ability (CR 114).

    Emblems exist only in the command zone and can never be moved or removed.
    """

    name: str = ""
    oracle_text: str = ""


@dataclass
class Effect:
    """Base class for all spell and ability effects.

    Concrete subclasses (DrawCards, DealDamage, CreateToken, etc.) are
    defined in engine/cards/effects.py (Phase E13). This base exists so
    StackObject can hold a typed reference from Phase E1 onward.
    """

    def resolve(self, _game: GameState, _source: GameObject) -> str:
        """Apply this effect and return a short resolution log detail."""
        return ""


@dataclass
class Target:
    """A single chosen target for a spell or ability (CR 115).

    Exactly one of obj_id or player_idx is set; the other is None.
    """

    obj_id: int | None = None
    player_idx: int | None = None


@dataclass
class Modifier:
    """A continuous effect currently applied to a permanent.

    Fully populated in Phase E9 (layer system). Stored on Permanent from
    Phase E1 so the data structure is complete from the start.
    """

    source_obj_id: int = 0
    layer: int = 7
    sublayer: str = ""
    timestamp: int = field(default_factory=_next_ts)
    duration: str = "permanent"


@dataclass
class Permanent(GameObject):
    """A card or token currently on the battlefield (CR 110.1).

    Power and toughness are not stored as raw integers here. The layer
    system (Phase E9) derives them from the source card plus all active
    modifiers. Until E9 is implemented, callers read directly from
    card_info.numeric_power / card_info.numeric_toughness plus counters.
    """

    source: CardObject | TokenObject | None = None
    tapped: bool = False
    flipped: bool = False
    face_down: bool = False
    phased_out: bool = False
    sick: bool = True
    attached_to: int | None = None
    counters: dict[str, int] = field(default_factory=dict)
    damage_marked: int = 0
    modifiers: list[Modifier] = field(default_factory=list)

    @property
    def is_token(self) -> bool:
        """True when this permanent was created as a token, not cast from a deck."""
        return isinstance(self.source, TokenObject)

    @property
    def card_info(self) -> CardInfo | None:
        """Static card data; None for tokens (they have no card_info)."""
        if isinstance(self.source, CardObject):
            return self.source.card_info
        return None

    @property
    def name(self) -> str:
        """Display name drawn from the underlying card or token blueprint."""
        if isinstance(self.source, CardObject) and self.source.card_info:
            return self.source.card_info.name
        if isinstance(self.source, TokenObject):
            return self.source.name
        return ""

    @property
    def type_line(self) -> str:
        """Full type line, e.g. 'Legendary Creature — Human Warrior'."""
        if isinstance(self.source, CardObject) and self.source.card_info:
            return self.source.card_info.type_line
        if isinstance(self.source, TokenObject):
            return self.source.type_line
        return ""

    @property
    def oracle_text(self) -> str:
        """Oracle text used by the rules engine for keyword and effect parsing."""
        if isinstance(self.source, CardObject) and self.source.card_info:
            return self.source.card_info.oracle_text
        if isinstance(self.source, TokenObject):
            return self.source.oracle_text
        return ""

    def has_keyword(self, keyword: str) -> bool:
        """Return True if the oracle text contains the given keyword (case-insensitive)."""
        return keyword.lower() in self.oracle_text.lower()

    def to_dict(self) -> dict:
        """Serialise this permanent for clients and integration tests."""
        power, toughness = _power_toughness(self)
        return {
            "objId": self.obj_id,
            "uid": str(self.obj_id),
            "name": self.name,
            "cmc": self.card_info.cmc if self.card_info is not None else 0,
            "type": self.type_line,
            "typeLine": self.type_line,
            "power": power,
            "toughness": toughness,
            "tapped": self.tapped,
            "sick": self.sick,
            "canAttack": _can_attack(self),
            "oracle": self.oracle_text,
            "counters": dict(self.counters),
            "damageMarked": self.damage_marked,
            "attachedTo": self.attached_to,
        }


@dataclass
class SpellOnStack(GameObject):
    """A spell that has been cast and placed on the stack (CR 112.1a)."""

    source: CardObject | None = None
    effect: Effect | None = None
    targets: list[Target] = field(default_factory=list)
    modes: list[int] = field(default_factory=list)
    chosen_x: int = 0


@dataclass
class ActivatedAbilityOnStack(GameObject):
    """An activated ability that has been put on the stack (CR 112.1b)."""

    source_permanent_id: int = 0
    ability_idx: int = 0
    effect: Effect | None = None
    targets: list[Target] = field(default_factory=list)


@dataclass
class TriggeredAbilityOnStack(GameObject):
    """A triggered ability waiting on the stack to resolve (CR 112.1c)."""

    source_permanent_id: int = 0
    trigger_key: str = ""
    effect: Effect | None = None
    targets: list[Target] = field(default_factory=list)


StackObject: TypeAlias = SpellOnStack | ActivatedAbilityOnStack | TriggeredAbilityOnStack


def _power_toughness(perm: Permanent) -> tuple[int, int]:
    """Return printed/token power and toughness without continuous effects."""
    if perm.card_info is not None:
        return perm.card_info.numeric_power, perm.card_info.numeric_toughness
    if isinstance(perm.source, TokenObject):
        return _parse_int(perm.source.power), _parse_int(perm.source.toughness)
    return 0, 0


def _parse_int(value: str) -> int:
    """Parse integer P/T text; variable values default to 0 in Phase A."""
    try:
        return int(value)
    except ValueError:
        return 0


def _can_attack(perm: Permanent) -> bool:
    """Return whether a permanent is eligible to attack in the simple Phase B loop."""
    return "Creature" in perm.type_line and not perm.tapped and not perm.sick
