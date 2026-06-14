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

from engine.core.sac_cast_flags import SacrificeCastFlags

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
    exiled_cast_mode: str | None = None
    suspend_time_counters: int = 0


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


ZoneCard: TypeAlias = CardObject | TokenObject


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

    def describe(self) -> str:
        """Return a short human-readable description of this effect."""
        return type(self).__name__


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
class _PermanentState:
    """Zone-status flags for a battlefield permanent."""

    tapped: bool = False
    flipped: bool = False
    face_down: bool = False
    phased_out: bool = False
    sick: bool = True


@dataclass
class Permanent(GameObject):
    """A card or token currently on the battlefield (CR 110.1).

    Power and toughness are not stored as raw integers here. The layer
    system (Phase E9) derives them from the source card plus all active
    modifiers. Until E9 is implemented, callers read directly from
    card_info.numeric_power / card_info.numeric_toughness plus counters.
    """

    source: CardObject | TokenObject | None = None
    state: _PermanentState = field(default_factory=_PermanentState)
    attached_to: int | None = None
    counters: dict[str, int] = field(default_factory=dict)
    damage_marked: int = 0
    modifiers: list[Modifier] = field(default_factory=list)

    @property
    def tapped(self) -> bool:
        """True when this permanent is tapped."""
        return self.state.tapped

    @tapped.setter
    def tapped(self, value: bool) -> None:
        """Set tapped status."""
        self.state.tapped = value

    @property
    def flipped(self) -> bool:
        """True when this permanent is flipped."""
        return self.state.flipped

    @flipped.setter
    def flipped(self, value: bool) -> None:
        """Set flipped status."""
        self.state.flipped = value

    @property
    def face_down(self) -> bool:
        """True when this permanent is face-down."""
        return self.state.face_down

    @face_down.setter
    def face_down(self, value: bool) -> None:
        """Set face-down status."""
        self.state.face_down = value

    @property
    def phased_out(self) -> bool:
        """True when this permanent is phased out."""
        return self.state.phased_out

    @phased_out.setter
    def phased_out(self, value: bool) -> None:
        """Set phased-out status."""
        self.state.phased_out = value

    @property
    def sick(self) -> bool:
        """True when this permanent has summoning sickness."""
        return self.state.sick

    @sick.setter
    def sick(self, value: bool) -> None:
        """Set summoning sickness."""
        self.state.sick = value

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
        return oracle_has_keyword(self.oracle_text, keyword)

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
            "faceDown": self.face_down,
            "sick": self.sick,
            "canAttack": _can_attack(self),
            "oracle": self.oracle_text,
            "counters": dict(self.counters),
            "damageMarked": self.damage_marked,
            "attachedTo": self.attached_to,
        }


@dataclass
class _GraveyardAlts:
    """Graveyard-based alternate cast modes."""

    flashback: bool = False
    escape: bool = False
    jump_start: bool = False
    retrace: bool = False
    aftermath: bool = False
    harmonize: bool = False
    disturb: bool = False


@dataclass
class _ExileAlts:
    """Exile-based alternate cast modes."""

    foretell: bool = False
    plot: bool = False
    madness: bool = False
    suspend: bool = False


@dataclass
class SpellAlternateCast:
    """Graveyard and exile alternate cast flags on a spell."""

    graveyard: _GraveyardAlts = field(default_factory=_GraveyardAlts)
    exile: _ExileAlts = field(default_factory=_ExileAlts)

    @property
    def flashback(self) -> bool:
        """True when cast via flashback."""
        return self.graveyard.flashback

    @flashback.setter
    def flashback(self, value: bool) -> None:
        """Set flashback flag."""
        self.graveyard.flashback = value

    @property
    def escape(self) -> bool:
        """True when cast via escape."""
        return self.graveyard.escape

    @escape.setter
    def escape(self, value: bool) -> None:
        """Set escape flag."""
        self.graveyard.escape = value

    @property
    def jump_start(self) -> bool:
        """True when cast via jump-start."""
        return self.graveyard.jump_start

    @jump_start.setter
    def jump_start(self, value: bool) -> None:
        """Set jump-start flag."""
        self.graveyard.jump_start = value

    @property
    def retrace(self) -> bool:
        """True when cast via retrace."""
        return self.graveyard.retrace

    @retrace.setter
    def retrace(self, value: bool) -> None:
        """Set retrace flag."""
        self.graveyard.retrace = value

    @property
    def aftermath(self) -> bool:
        """True when cast via aftermath."""
        return self.graveyard.aftermath

    @aftermath.setter
    def aftermath(self, value: bool) -> None:
        """Set aftermath flag."""
        self.graveyard.aftermath = value

    @property
    def foretell(self) -> bool:
        """True when cast via foretell."""
        return self.exile.foretell

    @foretell.setter
    def foretell(self, value: bool) -> None:
        """Set foretell flag."""
        self.exile.foretell = value

    @property
    def plot(self) -> bool:
        """True when cast via plot."""
        return self.exile.plot

    @plot.setter
    def plot(self, value: bool) -> None:
        """Set plot flag."""
        self.exile.plot = value

    @property
    def madness(self) -> bool:
        """True when cast via madness."""
        return self.exile.madness

    @madness.setter
    def madness(self, value: bool) -> None:
        """Set madness flag."""
        self.exile.madness = value

    @property
    def suspend(self) -> bool:
        """True when cast via suspend."""
        return self.exile.suspend

    @suspend.setter
    def suspend(self, value: bool) -> None:
        """Set suspend flag."""
        self.exile.suspend = value

    @property
    def disturb(self) -> bool:
        """True when cast via disturb."""
        return self.graveyard.disturb

    @disturb.setter
    def disturb(self, value: bool) -> None:
        """Set disturb flag."""
        self.graveyard.disturb = value

    @property
    def harmonize(self) -> bool:
        """True when cast via harmonize."""
        return self.graveyard.harmonize

    @harmonize.setter
    def harmonize(self, value: bool) -> None:
        """Set harmonize flag."""
        self.graveyard.harmonize = value


@dataclass
class _CostMods:
    """Cost modification payment flags."""

    kicker_times: int = 0
    entwined: bool = False
    overloaded: bool = False
    bestow: bool = False
    paid_buyback: bool = False


@dataclass
class _AlternateModes:
    """Alternate mode payment flags."""

    sac: SacrificeCastFlags = field(default_factory=SacrificeCastFlags)
    morph_face_down: bool = False


@dataclass
class _KeywordPays:
    """Keyword-related payment flags."""

    disguise_face_down: bool = False
    dash: bool = False
    blitz: bool = False
    cleave: bool = False
    conspire: bool = False
    demonstrate: bool = False
    awaken: bool = False


class SpellCastPayment:
    """Optional costs paid when a spell was announced."""

    def __init__(
        self,
        costs: _CostMods | None = None,
        modes: _AlternateModes | None = None,
        keywords: _KeywordPays | None = None,
    ) -> None:
        """Initialise payment flags grouped into sub-structs."""
        self.costs = costs if costs is not None else _CostMods()
        self.modes = modes if modes is not None else _AlternateModes()
        self.keywords = keywords if keywords is not None else _KeywordPays()

    @property
    def kicker_times(self) -> int:
        """Number of times kicker was paid."""
        return self.costs.kicker_times

    @kicker_times.setter
    def kicker_times(self, value: int) -> None:
        """Set kicker count."""
        self.costs.kicker_times = value

    @property
    def entwined(self) -> bool:
        """True when entwine was paid."""
        return self.costs.entwined

    @entwined.setter
    def entwined(self, value: bool) -> None:
        """Set entwine flag."""
        self.costs.entwined = value

    @property
    def overloaded(self) -> bool:
        """True when overload was paid."""
        return self.costs.overloaded

    @overloaded.setter
    def overloaded(self, value: bool) -> None:
        """Set overload flag."""
        self.costs.overloaded = value

    @property
    def bestow(self) -> bool:
        """True when bestow was paid."""
        return self.costs.bestow

    @bestow.setter
    def bestow(self, value: bool) -> None:
        """Set bestow flag."""
        self.costs.bestow = value

    @property
    def paid_buyback(self) -> bool:
        """True when buyback was paid."""
        return self.costs.paid_buyback

    @paid_buyback.setter
    def paid_buyback(self, value: bool) -> None:
        """Set paid_buyback flag."""
        self.costs.paid_buyback = value

    @property
    def emerge(self) -> bool:
        """True when emerge was paid."""
        return self.modes.sac.emerge

    @emerge.setter
    def emerge(self, value: bool) -> None:
        """Set emerge flag."""
        self.modes.sac.emerge = value

    @property
    def evoke(self) -> bool:
        """True when evoke was paid."""
        return self.modes.sac.evoke

    @evoke.setter
    def evoke(self, value: bool) -> None:
        """Set evoke flag."""
        self.modes.sac.evoke = value

    @property
    def mutate(self) -> bool:
        """True when mutate was paid."""
        return self.modes.sac.mutate

    @mutate.setter
    def mutate(self, value: bool) -> None:
        """Set mutate flag."""
        self.modes.sac.mutate = value

    @property
    def casualty(self) -> bool:
        """True when casualty was paid."""
        return self.modes.sac.casualty

    @casualty.setter
    def casualty(self, value: bool) -> None:
        """Set casualty flag."""
        self.modes.sac.casualty = value

    @property
    def bargain(self) -> bool:
        """True when bargain was paid."""
        return self.modes.sac.bargain

    @bargain.setter
    def bargain(self, value: bool) -> None:
        """Set bargain flag."""
        self.modes.sac.bargain = value

    @property
    def gift(self) -> bool:
        """True when gift was paid."""
        return self.modes.sac.gift

    @gift.setter
    def gift(self, value: bool) -> None:
        """Set gift flag."""
        self.modes.sac.gift = value

    @property
    def morph_face_down(self) -> bool:
        """True when cast face-down via morph."""
        return self.modes.morph_face_down

    @morph_face_down.setter
    def morph_face_down(self, value: bool) -> None:
        """Set morph face-down flag."""
        self.modes.morph_face_down = value

    @property
    def disguise_face_down(self) -> bool:
        """True when cast face-down via disguise."""
        return self.keywords.disguise_face_down

    @disguise_face_down.setter
    def disguise_face_down(self, value: bool) -> None:
        """Set disguise face-down flag."""
        self.keywords.disguise_face_down = value

    @property
    def dash(self) -> bool:
        """True when dash was paid."""
        return self.keywords.dash

    @dash.setter
    def dash(self, value: bool) -> None:
        """Set dash flag."""
        self.keywords.dash = value

    @property
    def blitz(self) -> bool:
        """True when blitz was paid."""
        return self.keywords.blitz

    @blitz.setter
    def blitz(self, value: bool) -> None:
        """Set blitz flag."""
        self.keywords.blitz = value

    @property
    def cleave(self) -> bool:
        """True when cleave was paid."""
        return self.keywords.cleave

    @cleave.setter
    def cleave(self, value: bool) -> None:
        """Set cleave flag."""
        self.keywords.cleave = value

    @property
    def conspire(self) -> bool:
        """True when conspire was paid."""
        return self.keywords.conspire

    @conspire.setter
    def conspire(self, value: bool) -> None:
        """Set conspire flag."""
        self.keywords.conspire = value

    @property
    def demonstrate(self) -> bool:
        """True when demonstrate was paid."""
        return self.keywords.demonstrate

    @demonstrate.setter
    def demonstrate(self, value: bool) -> None:
        """Set demonstrate flag."""
        self.keywords.demonstrate = value

    @property
    def awaken(self) -> bool:
        """True when awaken was paid."""
        return self.keywords.awaken

    @awaken.setter
    def awaken(self, value: bool) -> None:
        """Set awaken flag."""
        self.keywords.awaken = value


@dataclass
class _SpellCopy:
    """Copy-creating keyword flags."""

    storm: bool = False
    replicate: bool = False
    gravestorm: bool = False


@dataclass
class SpellStackCopyFlags:
    """Storm, replicate, and cascade copy markers."""

    copy_source: _SpellCopy = field(default_factory=_SpellCopy)
    cascade: bool = False
    casualty: bool = False
    cleave: bool = False
    conspire: bool = False
    demonstrate: bool = False
    fuse: bool = False


    @property
    def storm(self) -> bool:
        """True when this is a storm copy."""
        return self.copy_source.storm

    @storm.setter
    def storm(self, value: bool) -> None:
        """Set storm flag."""
        self.copy_source.storm = value

    @property
    def replicate(self) -> bool:
        """True when this is a replicate copy."""
        return self.copy_source.replicate

    @replicate.setter
    def replicate(self, value: bool) -> None:
        """Set replicate flag."""
        self.copy_source.replicate = value


@dataclass
class _SpellCasting:
    """Cast mode and copy flags for a spell on the stack."""

    alternate: SpellAlternateCast = field(default_factory=SpellAlternateCast)
    payment: SpellCastPayment = field(default_factory=SpellCastPayment)
    copies: SpellStackCopyFlags = field(default_factory=SpellStackCopyFlags)
    awaken_land_hand_idx: int | None = None


@dataclass
class SpellOnStack(GameObject):
    """A spell that has been cast and placed on the stack (CR 112.1a)."""

    source: CardObject | None = None
    effect: Effect | None = None
    targets: list[Target] = field(default_factory=list)
    modes: list[int] = field(default_factory=list)
    chosen_x: int = 0
    casting: _SpellCasting = field(default_factory=_SpellCasting)

    @property
    def alternate(self) -> SpellAlternateCast:
        """Alternate cast flags for this spell."""
        return self.casting.alternate

    @property
    def payment(self) -> SpellCastPayment:
        """Payment flags for this spell."""
        return self.casting.payment

    @property
    def copies(self) -> SpellStackCopyFlags:
        """Copy-trigger flags for this spell."""
        return self.casting.copies


def spell_is_ephemeral_copy(spell: SpellOnStack) -> bool:
    """Return True when a stack copy should not move its source card to a zone."""
    return (
        spell.copies.storm
        or spell.copies.replicate
        or spell.copies.casualty
        or spell.copies.cleave
        or spell.copies.conspire
        or spell.copies.demonstrate
    )


def spell_exiles_from_graveyard_cast(spell: SpellOnStack) -> bool:
    """Return True when a graveyard alt-cast spell exiles on leaving the stack."""
    alt = spell.alternate
    return (
        alt.flashback
        or alt.escape
        or alt.jump_start
        or alt.aftermath
        or alt.disturb
        or alt.harmonize
    )


def spell_returns_to_hand_on_resolve(spell: SpellOnStack) -> bool:
    """Return True when a resolved spell returns to its owner's hand (buyback)."""
    return spell.payment.paid_buyback and not spell_is_ephemeral_copy(spell)


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
    if perm.face_down:
        return 2, 2
    if perm.card_info is not None:
        return perm.card_info.numeric_power, perm.card_info.numeric_toughness
    if isinstance(perm.source, TokenObject):
        return _parse_int(perm.source.power), _parse_int(perm.source.toughness)
    return 0, 0


def effective_power(perm: Permanent) -> int:
    """Return combat power including counters and face-down 2/2 stats."""
    power, _ = _power_toughness(perm)
    return (
        power
        + perm.counters.get('+1/+1', 0)
        + perm.counters.get('+power/+0', 0)
        - perm.counters.get('-1/-1', 0)
    )


def effective_toughness(perm: Permanent) -> int:
    """Return combat toughness including counters and face-down 2/2 stats."""
    _, toughness = _power_toughness(perm)
    return toughness + perm.counters.get('+1/+1', 0) - perm.counters.get('-1/-1', 0)


def _parse_int(value: str) -> int:
    """Parse integer P/T text; variable values default to 0 in Phase A."""
    try:
        return int(value)
    except ValueError:
        return 0


def oracle_has_keyword(oracle_text: str, keyword: str) -> bool:
    """Return True when oracle text contains the keyword (case-insensitive)."""
    return keyword.lower() in oracle_text.lower()


def _can_attack(perm: Permanent) -> bool:
    """Return whether a permanent is eligible to attack in the simple Phase B loop."""
    return (
        "Creature" in perm.type_line
        and not perm.tapped
        and not perm.sick
        and not oracle_has_keyword(perm.oracle_text, "defender")
    )
