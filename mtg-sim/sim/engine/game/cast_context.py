"""Cast announce types and stack placement helpers (no game-package cycles)."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.core.game_object import (
    CardObject,
    SpellAlternateCast,
    SpellCastPayment,
    SpellOnStack,
    SpellStackCopyFlags,
    Target,
    _SpellCasting,
)
from engine.game.face_alternate_cast import FaceAlternateCastFlags


@dataclass(frozen=True)
class _RepeatCostChoices:
    """Integer repeat costs such as kicker and replicate."""

    kicker_times: int = 0
    replicate_times: int = 0


@dataclass(frozen=True)
class _PaidCastExtras:
    """Optional spell payments that do not fit other sacrifice groups."""

    paid_awaken: bool = False
    paid_impending: bool = False
    paid_for_mirrodin: bool = False


@dataclass(frozen=True)
class _PaidSacrificeCosts:
    """Optional sacrifice payments announced with a cast."""

    paid_casualty: bool = False
    paid_conspire: bool = False
    paid_bargain: bool = False
    paid_demonstrate: bool = False
    paid_gift: bool = False
    paid_fuse: bool = False
    cast_extras: _PaidCastExtras = field(default_factory=_PaidCastExtras)


@dataclass(frozen=True)
class HandCastCostChoices:
    """Stackable optional costs (kicker, entwine, overload, etc.)."""

    entwined: bool = False
    overloaded: bool = False
    paid_buyback: bool = False
    repeat: _RepeatCostChoices = field(default_factory=_RepeatCostChoices)
    paid: _PaidSacrificeCosts = field(default_factory=_PaidSacrificeCosts)

    @property
    def kicker_times(self) -> int:
        """Number of times kicker was paid."""
        return self.repeat.kicker_times

    @property
    def replicate_times(self) -> int:
        """Number of times replicate was paid."""
        return self.repeat.replicate_times

    @property
    def paid_casualty(self) -> bool:
        """Whether casualty was paid."""
        return self.paid.paid_casualty

    @property
    def paid_conspire(self) -> bool:
        """Whether conspire was paid."""
        return self.paid.paid_conspire

    @property
    def paid_bargain(self) -> bool:
        """Whether bargain was paid."""
        return self.paid.paid_bargain

    @property
    def paid_demonstrate(self) -> bool:
        """Whether demonstrate was paid."""
        return self.paid.paid_demonstrate

    @property
    def paid_awaken(self) -> bool:
        """Whether awaken was paid."""
        return self.paid.cast_extras.paid_awaken

    @property
    def paid_gift(self) -> bool:
        """Whether gift was paid."""
        return self.paid.paid_gift

    @property
    def paid_fuse(self) -> bool:
        """Whether fuse was paid."""
        return self.paid.paid_fuse

    @property
    def paid_impending(self) -> bool:
        """Whether impending was paid."""
        return self.paid.cast_extras.paid_impending

    @property
    def paid_for_mirrodin(self) -> bool:
        """Whether For Mirrodin! was paid."""
        return self.paid.cast_extras.paid_for_mirrodin


@dataclass(frozen=True)
class _CostConditionAlts:
    """Alternate cast modes that modify cost based on a condition."""

    cast_for_miracle: bool = False
    cast_for_freerunning: bool = False
    cast_for_spectacle: bool = False
    cast_for_surge: bool = False


@dataclass(frozen=True)
class HandAlternateCastChoices:
    """Alternate cast modes announced from hand."""

    cast_for_emerge: bool = False
    cast_for_evoke: bool = False
    cast_for_mutate: bool = False
    cast_for_cleave: bool = False
    cast_for_offering: bool = False
    face: FaceAlternateCastFlags = field(default_factory=FaceAlternateCastFlags)
    conditions: _CostConditionAlts = field(default_factory=_CostConditionAlts)

    @property
    def cast_for_miracle(self) -> bool:
        """Whether this cast uses miracle."""
        return self.conditions.cast_for_miracle

    @property
    def cast_for_freerunning(self) -> bool:
        """Whether this cast uses freerunning."""
        return self.conditions.cast_for_freerunning

    @property
    def cast_for_spectacle(self) -> bool:
        """Whether this cast uses spectacle."""
        return self.conditions.cast_for_spectacle

    @property
    def cast_for_surge(self) -> bool:
        """Whether this cast uses surge."""
        return self.conditions.cast_for_surge

    @property
    def cast_for_morph(self) -> bool:
        """Whether this cast uses morph (face-down)."""
        return self.face.cast_for_morph

    @property
    def cast_for_disguise(self) -> bool:
        """Whether this cast uses disguise (face-down)."""
        return self.face.cast_for_disguise

    @property
    def cast_for_dash(self) -> bool:
        """Whether this cast uses dash."""
        return self.face.cast_for_dash

    @property
    def cast_for_blitz(self) -> bool:
        """Whether this cast uses blitz."""
        return self.face.cast_for_blitz


@dataclass(frozen=True)
class _SacrificeTargetIds:
    """Permanent ids sacrificed for emerge, casualty, or bargain."""

    emerge_sacrifice_ids: tuple[int, ...] = ()
    casualty_sacrifice_ids: tuple[int, ...] = ()
    bargain_sacrifice_ids: tuple[int, ...] = ()
    offering_sacrifice_ids: tuple[int, ...] = ()
    for_mirrodin_sacrifice_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class CastTargetingIds:
    """Target and mode indices for optional costs."""

    bestow_target_uid: str | None = None
    mutate_target_uid: str | None = None
    spree_mode_indices: tuple[int, ...] = ()
    harmonize_creature_ids: tuple[int, ...] = ()
    escalate_extra_targets: int = 0
    sacrifices: _SacrificeTargetIds = field(default_factory=_SacrificeTargetIds)

    @property
    def emerge_sacrifice_ids(self) -> tuple[int, ...]:
        """Permanent ids sacrificed for emerge."""
        return self.sacrifices.emerge_sacrifice_ids

    @property
    def casualty_sacrifice_ids(self) -> tuple[int, ...]:
        """Permanent ids sacrificed for casualty."""
        return self.sacrifices.casualty_sacrifice_ids

    @property
    def bargain_sacrifice_ids(self) -> tuple[int, ...]:
        """Permanent ids sacrificed for bargain."""
        return self.sacrifices.bargain_sacrifice_ids

    @property
    def offering_sacrifice_ids(self) -> tuple[int, ...]:
        """Permanent ids sacrificed for offering."""
        return self.sacrifices.offering_sacrifice_ids

    @property
    def for_mirrodin_sacrifice_ids(self) -> tuple[int, ...]:
        """Permanent ids sacrificed for For Mirrodin!."""
        return self.sacrifices.for_mirrodin_sacrifice_ids


@dataclass(frozen=True)
class CastManaReductionIds:
    """Ids for convoke, delve, improvise, and similar reductions."""

    convoke_creature_ids: tuple[int, ...] = ()
    delve_graveyard_indices: tuple[int, ...] = ()
    improvise_artifact_ids: tuple[int, ...] = ()
    sneak_land_hand_indices: tuple[int, ...] = ()
    assist_mana: int = 0
    awaken_land_hand_idx: int | None = None


@dataclass(frozen=True)
class CastModifierIds:
    """Targeting and payment helper ids for announcing a cast."""

    targeting: CastTargetingIds = field(default_factory=CastTargetingIds)
    reductions: CastManaReductionIds = field(default_factory=CastManaReductionIds)


@dataclass(frozen=True)
class CastAnnounceOptions:
    """Optional costs when announcing a cast from hand."""

    costs: HandCastCostChoices = field(default_factory=HandCastCostChoices)
    alternate: HandAlternateCastChoices = field(default_factory=HandAlternateCastChoices)
    modifiers: CastModifierIds = field(default_factory=CastModifierIds)


@dataclass(frozen=True)
class _HandCastExtras:
    """Extra hand-cast options that do not fit payment flags."""

    awaken_land_hand_idx: int | None = None
    fuse: bool = False
    impending: bool = False


@dataclass(frozen=True)
class SpellCastContext:
    """Options when placing a spell on the stack."""

    from_graveyard: bool = False
    from_exile: bool = False
    alternate: SpellAlternateCast = field(default_factory=SpellAlternateCast)
    payment: SpellCastPayment = field(default_factory=SpellCastPayment)
    replicate_times: int = 0
    spree_mode_indices: tuple[int, ...] = ()
    extras: _HandCastExtras = field(default_factory=_HandCastExtras)

    @property
    def awaken_land_hand_idx(self) -> int | None:
        """Hand index of the land chosen for awaken."""
        return self.extras.awaken_land_hand_idx

    @property
    def fuse(self) -> bool:
        """Whether fuse was paid."""
        return self.extras.fuse

    @property
    def impending(self) -> bool:
        """Whether impending was paid."""
        return self.extras.impending


def spell_on_stack_from_context(
    controller_idx: int,
    card: CardObject,
    targets: list[Target],
    context: SpellCastContext,
    *,
    copy_flags: SpellStackCopyFlags | None = None,
) -> SpellOnStack:
    """Build a SpellOnStack from announce/stack placement context."""
    return SpellOnStack(
        controller_idx=controller_idx,
        owner_idx=card.owner_idx,
        source=card,
        targets=targets,
        modes=list(context.spree_mode_indices),
        casting=_SpellCasting(
            alternate=context.alternate,
            payment=context.payment,
            copies=copy_flags or SpellStackCopyFlags(),
            awaken_land_hand_idx=context.awaken_land_hand_idx,
            impending=context.impending,
        ),
    )
