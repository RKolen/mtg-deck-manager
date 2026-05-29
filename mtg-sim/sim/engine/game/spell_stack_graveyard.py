"""Graveyard, foretell, and plot casting for SpellStackMixin."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.abilities.keywords.casting.disturb import (
    can_cast_via_disturb,
    disturb_mana_needed,
    has_disturb,
)
from engine.abilities.keywords.casting.harmonize import (
    can_cast_via_harmonize,
    has_harmonize,
    normalize_harmonize_creature_id,
    resolve_harmonize_mana,
)
from engine.abilities.keywords.casting import (
    FORETELL_SETUP_MANA,
    aftermath_mana_needed,
    auto_escape_exile_indices,
    can_cast_aftermath,
    can_cast_via_escape,
    can_cast_via_flashback,
    can_cast_via_jump_start,
    can_cast_via_retrace,
    cast_from_foretell_exile,
    cast_from_plot_exile,
    discard_for_jump_start,
    discard_land_for_retrace,
    escape_mana_needed,
    escape_payment_error,
    exile_for_escape_cost,
    exile_for_foretell,
    exile_for_plot,
    flashback_mana_needed,
    foretell_cast_mana_needed,
    foretell_setup_error,
    foretold_cast_error,
    has_aftermath,
    has_escape,
    has_flashback,
    has_jump_start,
    has_retrace,
    jump_start_discard_error,
    jump_start_mana_needed,
    plot_setup_error,
    plotted_cast_error,
    retrace_land_discard_error,
    retrace_life_cost,
    retrace_mana_needed,
)
from engine.core.game_object import CardObject, SpellAlternateCast
from engine.game.cast_flow import ExileCastRequest, GraveyardCastRequest
from engine.game.helpers import require_card_info
from engine.game.spell_stack_placement import SpellStackPlacementMixin


@dataclass
class _HarmonizeCastState:
    mana: int = 0
    life: int = 0
    creature_id: int | None = None


@dataclass
class _EscapeCastState:
    exiled: list[int] = field(default_factory=list)


@dataclass
class _DiscardCastState:
    discarded: CardObject | None = None


@dataclass
class _RetraceCastState:
    discarded: CardObject | None = None
    life: int = 0


class GraveyardCastMixin(SpellStackPlacementMixin):
    """Cast from graveyard, foretell setup/cast, and plot setup/cast."""

    def _announce_flashback_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
    ) -> dict:
        """Pay flashback cost and cast a card from the graveyard."""
        return self._announce_graveyard_spell(
            graveyard_idx,
            target_uid_str,
            target_player_idx,
            auto_resolve,
            GraveyardCastRequest(
                player_idx=0,
                has_keyword=has_flashback,
                keyword_error=lambda c: f"{c.name} does not have flashback",
                can_cast=lambda c: can_cast_via_flashback(
                    c, self.phase, self.state.stack.is_empty,
                ),
                timing_error="Cannot cast flashback now",
                mana_cost=flashback_mana_needed,
                alternate=SpellAlternateCast(flashback=True),
                log_action="flashback",
                log_detail=lambda c: f"{c.name} on stack",
            ),
        )

    def _announce_harmonize_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
        harmonize_creature_ids: list[int] | None = None,
    ) -> dict:
        """Pay harmonize cost and cast a card from the graveyard."""
        creature_ids = list(harmonize_creature_ids or [])
        harmonize_state = _HarmonizeCastState()

        def prepay_harmonize(_card: CardObject, card_info) -> str | None:
            creature_id = normalize_harmonize_creature_id(card_info, creature_ids)
            mana_needed, life_cost, tap_err = resolve_harmonize_mana(
                card_info,
                self.state.zones,
                0,
                creature_id,
            )
            if tap_err:
                return tap_err
            harmonize_state.mana = mana_needed
            harmonize_state.life = life_cost
            harmonize_state.creature_id = creature_id
            return None

        def harmonize_mana(_card_info):
            return harmonize_state.mana, harmonize_state.life

        def harmonize_detail(card_info):
            tap_note = (
                " (creature tapped for cost reduction)"
                if harmonize_state.creature_id
                else ""
            )
            return f"{card_info.name} on stack{tap_note}"

        return self._announce_graveyard_spell(
            graveyard_idx,
            target_uid_str,
            target_player_idx,
            auto_resolve,
            GraveyardCastRequest(
                player_idx=0,
                has_keyword=has_harmonize,
                keyword_error=lambda c: f"{c.name} does not have harmonize",
                can_cast=lambda c: can_cast_via_harmonize(
                    c, self.phase, self.state.stack.is_empty,
                ),
                timing_error="Cannot cast harmonize now",
                mana_cost=harmonize_mana,
                alternate=SpellAlternateCast(harmonize=True),
                log_action="harmonize",
                log_detail=harmonize_detail,
                prepay=prepay_harmonize,
            ),
        )

    def _announce_disturb_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
    ) -> dict:
        """Pay disturb cost and cast a creature from the graveyard."""
        return self._announce_graveyard_spell(
            graveyard_idx,
            target_uid_str,
            target_player_idx,
            auto_resolve,
            GraveyardCastRequest(
                player_idx=0,
                has_keyword=has_disturb,
                keyword_error=lambda c: f"{c.name} does not have disturb",
                can_cast=lambda c: can_cast_via_disturb(
                    c, self.phase, self.state.stack.is_empty,
                ),
                timing_error="Cannot cast disturb now",
                mana_cost=disturb_mana_needed,
                alternate=SpellAlternateCast(disturb=True),
                log_action="disturb",
                log_detail=lambda c: f"{c.name} on stack (disturb)",
            ),
        )

    def _announce_aftermath_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
    ) -> dict:
        """Pay mana and cast an aftermath card from the graveyard."""
        return self._announce_graveyard_spell(
            graveyard_idx,
            target_uid_str,
            target_player_idx,
            auto_resolve,
            GraveyardCastRequest(
                player_idx=0,
                has_keyword=has_aftermath,
                keyword_error=lambda c: f"{c.name} does not have aftermath",
                can_cast=lambda c: can_cast_aftermath(
                    c, self.phase, self.state.stack.is_empty,
                ),
                timing_error="Cannot cast aftermath now",
                mana_cost=aftermath_mana_needed,
                alternate=SpellAlternateCast(aftermath=True),
                log_action="aftermath",
                log_detail=lambda c: f"{c.name} on stack",
            ),
        )

    def _announce_escape_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
        escape_exile_indices: list[int] | None = None,
    ) -> dict:
        """Pay escape costs and cast a card from the graveyard."""
        exile_indices = list(escape_exile_indices or [])
        escape_state = _EscapeCastState()

        def prepay_escape(_card: CardObject, card_info) -> str | None:
            indices = exile_indices
            if not indices:
                indices = auto_escape_exile_indices(
                    self.state.zones,
                    0,
                    graveyard_idx,
                    card_info,
                )
            exile_err = escape_payment_error(
                self.state.zones,
                0,
                graveyard_idx,
                indices,
                card_info,
            )
            if exile_err:
                return exile_err
            exiled = exile_for_escape_cost(
                self.state.zones,
                0,
                indices,
                card_info,
            )
            escape_state.exiled = exiled
            return None

        def escape_detail(card_info):
            detail = f"{card_info.name} on stack"
            if escape_state.exiled:
                detail = f"{detail} (escape, exiled {len(escape_state.exiled)} for cost)"
            return detail

        return self._announce_graveyard_spell(
            graveyard_idx,
            target_uid_str,
            target_player_idx,
            auto_resolve,
            GraveyardCastRequest(
                player_idx=0,
                has_keyword=has_escape,
                keyword_error=lambda c: f"{c.name} does not have escape",
                can_cast=lambda c: can_cast_via_escape(
                    c, self.phase, self.state.stack.is_empty,
                ),
                timing_error="Cannot cast escape now",
                mana_cost=escape_mana_needed,
                alternate=SpellAlternateCast(escape=True),
                log_action="escape",
                log_detail=escape_detail,
                prepay=prepay_escape,
            ),
        )

    def _announce_jump_start_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
        discard_hand_idx: int | None = None,
    ) -> dict:
        """Discard a card, pay jump-start cost, and cast from the graveyard."""
        jump_state = _DiscardCastState()

        def prepay_jump(_card: CardObject, _card_info) -> str | None:
            discard_err = jump_start_discard_error(
                self.state.zones, 0, discard_hand_idx,
            )
            if discard_err:
                return discard_err
            assert discard_hand_idx is not None
            jump_state.discarded = discard_for_jump_start(
                self.state.zones, 0, discard_hand_idx,
            )
            return None

        def jump_detail(card_info):
            assert jump_state.discarded is not None
            discard_info = require_card_info(jump_state.discarded)
            return f"{card_info.name} on stack (discarded {discard_info.name})"

        return self._announce_graveyard_spell(
            graveyard_idx,
            target_uid_str,
            target_player_idx,
            auto_resolve,
            GraveyardCastRequest(
                player_idx=0,
                has_keyword=has_jump_start,
                keyword_error=lambda c: f"{c.name} does not have jump-start",
                can_cast=lambda c: can_cast_via_jump_start(
                    c, self.phase, self.state.stack.is_empty,
                ),
                timing_error="Cannot cast jump-start now",
                mana_cost=jump_start_mana_needed,
                alternate=SpellAlternateCast(jump_start=True),
                log_action="jump-start",
                log_detail=jump_detail,
                prepay=prepay_jump,
            ),
        )

    def _announce_retrace_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
        discard_hand_idx: int | None = None,
    ) -> dict:
        """Discard a land, pay the spell's mana cost, and cast from the graveyard."""
        retrace_state = _RetraceCastState()

        def prepay_retrace(_card: CardObject, card_info) -> str | None:
            discard_err = retrace_land_discard_error(
                self.state.zones, 0, discard_hand_idx,
            )
            if discard_err:
                return discard_err
            assert discard_hand_idx is not None
            retrace_state.discarded = discard_land_for_retrace(
                self.state.zones, 0, discard_hand_idx,
            )
            retrace_state.life = retrace_life_cost(card_info)
            return None

        def retrace_mana_with_life(card_info):
            return retrace_mana_needed(card_info), retrace_state.life

        def retrace_detail(card_info):
            assert retrace_state.discarded is not None
            discard_info = require_card_info(retrace_state.discarded)
            return f"{card_info.name} on stack (discarded {discard_info.name})"

        return self._announce_graveyard_spell(
            graveyard_idx,
            target_uid_str,
            target_player_idx,
            auto_resolve,
            GraveyardCastRequest(
                player_idx=0,
                has_keyword=has_retrace,
                keyword_error=lambda c: f"{c.name} does not have retrace",
                can_cast=lambda c: can_cast_via_retrace(
                    c, self.phase, self.state.stack.is_empty,
                ),
                timing_error="Cannot cast retrace now",
                mana_cost=retrace_mana_with_life,
                alternate=SpellAlternateCast(retrace=True),
                log_action="retrace",
                log_detail=retrace_detail,
                prepay=prepay_retrace,
            ),
        )

    def action_foretell(self, hand_idx: int) -> dict:
        """Exile a card from hand for its foretell cost during a main phase."""
        card = self._zones(0).hand[hand_idx]
        if not isinstance(card, CardObject):
            return self._client_error("Invalid card")
        card_info = require_card_info(card)
        setup_err = foretell_setup_error(
            self.state.zones,
            0,
            hand_idx,
            card_info,
            self.phase,
            self.state.stack.is_empty,
        )
        if setup_err:
            return self._client_error(setup_err)
        mana_err = self._tap_mana_or_error(0, FORETELL_SETUP_MANA)
        if mana_err is not None:
            return mana_err
        exile_for_foretell(self.state.zones, 0, hand_idx)
        self._log("player", "foretell", f"Foretold {card_info.name}")
        return self.to_client()

    def _announce_cast_foretell(
        self,
        exile_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
    ) -> dict:
        """Cast a foretold card from exile for its foretell cost."""
        card, card_info, err = self._exile_card_checked(0, exile_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        cast_err = foretold_cast_error(
            self.state.zones,
            0,
            exile_idx,
            card_info,
            self.phase,
            self.state.stack.is_empty,
        )
        if cast_err:
            return self._client_error(cast_err)
        mana_needed, life_cost = foretell_cast_mana_needed(card_info)
        mana_err = self._tap_mana_or_error(0, mana_needed)
        if mana_err is not None:
            return mana_err
        card = cast_from_foretell_exile(self.state.zones, 0, exile_idx)
        return self._complete_announce_cast(
            self._exile_announce_completion(
                ExileCastRequest(
                    card=card,
                    card_info=card_info,
                    target_uid_str=target_uid_str,
                    target_player_idx=target_player_idx,
                    auto_resolve=auto_resolve,
                    alternate=SpellAlternateCast(foretell=True),
                    log_detail=f"{card_info.name} on stack (foretell)",
                    life_cost=life_cost,
                ),
            ),
        )

    def action_plot(self, hand_idx: int) -> dict:
        """Exile a sorcery from hand to plot it during a main phase."""
        card = self._zones(0).hand[hand_idx]
        if not isinstance(card, CardObject):
            return self._client_error("Invalid card")
        card_info = require_card_info(card)
        setup_err = plot_setup_error(
            self.state.zones,
            0,
            hand_idx,
            card_info,
            self.phase,
            self.state.stack.is_empty,
        )
        if setup_err:
            return self._client_error(setup_err)
        exile_for_plot(self.state.zones, 0, hand_idx)
        self._log("player", "plot", f"Plotted {card_info.name}")
        return self.to_client()

    def _announce_cast_plot(
        self,
        exile_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
    ) -> dict:
        """Cast a plotted sorcery from exile without paying mana."""
        card, card_info, err = self._exile_card_checked(0, exile_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        cast_err = plotted_cast_error(
            self.state.zones,
            0,
            exile_idx,
            card_info,
            self.phase,
            self.state.stack.is_empty,
        )
        if cast_err:
            return self._client_error(cast_err)
        card = cast_from_plot_exile(self.state.zones, 0, exile_idx)
        return self._complete_announce_cast(
            self._exile_announce_completion(
                ExileCastRequest(
                    card=card,
                    card_info=card_info,
                    target_uid_str=target_uid_str,
                    target_player_idx=target_player_idx,
                    auto_resolve=auto_resolve,
                    alternate=SpellAlternateCast(plot=True),
                    log_detail=f"{card_info.name} on stack (plot)",
                ),
            ),
        )
