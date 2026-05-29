"""Stack placement shared by hand, graveyard, and exile casts."""

from __future__ import annotations

from engine.core.game_object import CardObject, Target
from engine.game.cast_flow import (
    AnnounceCastCompletion,
    ExileCastRequest,
    GraveyardCastRequest,
    not_enough_mana_message,
    split_mana_cost,
)
from engine.game.cast_modifiers import apply_post_cast_modifiers
from engine.game.helpers import (
    SpellCastContext,
    require_card_info,
    spell_on_stack_from_context,
    targets_from_request,
)
from engine.game.runtime import GameRuntimeMixin


class SpellStackPlacementMixin(GameRuntimeMixin):
    """Move cast spells onto the stack and apply storm/cascade copies."""

    def _put_spell_on_stack(
        self,
        player_idx: int,
        card: CardObject,
        target_uid_str: str | None,
        target_player_idx: int | None,
        context: SpellCastContext | None = None,
    ) -> list[Target]:
        """Move a cast spell onto the stack."""
        opts = context or SpellCastContext()
        targets = targets_from_request(target_uid_str, target_player_idx)
        if opts.from_graveyard:
            self.state.zones.cast_from_graveyard(card, player_idx)
        elif not opts.from_exile:
            self.state.zones.play_from_hand(card, player_idx)
        self.state.stack.push(spell_on_stack_from_context(
            player_idx,
            card,
            targets,
            opts,
        ))
        actor = "player" if player_idx == 0 else "opponent"
        for detail in apply_post_cast_modifiers(self.state, player_idx, card, targets, opts):
            self._log(actor, "storm" if "storm" in detail else "cascade", detail)
        self.state.turn.action_taken()
        return targets

    def _tap_mana_or_error(self, player_idx: int, mana_needed: int) -> dict | None:
        """Tap lands for mana; return a client error dict when payment fails."""
        if self._tap_lands_for_mana(player_idx, mana_needed):
            return None
        return self._client_error(
            not_enough_mana_message(self._available_mana(player_idx), mana_needed),
        )

    def _pay_phyrexian(self, player_idx: int, life_cost: int, card_name: str) -> None:
        """Pay phyrexian life for a cast when applicable."""
        if life_cost:
            self.state.players[player_idx].life -= life_cost
            self._log("player", "phyrexian", f"Paid {life_cost} life for {card_name}")

    def _exile_announce_completion(
        self,
        request: ExileCastRequest,
    ) -> AnnounceCastCompletion:
        """Build completion args for a spell cast from exile."""
        return AnnounceCastCompletion(
            card=request.card,
            card_info=request.card_info,
            player_idx=0,
            target_uid_str=request.target_uid_str,
            target_player_idx=request.target_player_idx,
            context=SpellCastContext(
                alternate=request.alternate,
                from_exile=True,
            ),
            log_action="cast",
            log_detail=request.log_detail,
            auto_resolve=request.auto_resolve,
            life_cost=request.life_cost,
        )

    def _complete_announce_cast(self, completion: AnnounceCastCompletion) -> dict:
        """Increment cast count, place the spell, log, and optionally auto-pass."""
        card = completion.card
        card_info = completion.card_info
        player_idx = completion.player_idx
        self.state.players[player_idx].spells_cast_this_turn += 1
        self._pay_phyrexian(player_idx, completion.life_cost, card_info.name)
        targets = self._put_spell_on_stack(
            player_idx,
            card,
            completion.target_uid_str,
            completion.target_player_idx,
            context=completion.context,
        )
        actor = "player" if player_idx == 0 else "opponent"
        self._log(actor, completion.log_action, completion.log_detail)
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        if completion.auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

    def _announce_graveyard_spell(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
        request: GraveyardCastRequest,
    ) -> dict:
        """Validate, pay, and cast a spell from the graveyard."""
        card, err = self._graveyard_card_checked(request.player_idx, graveyard_idx)
        if err is not None:
            return err
        assert card is not None
        card_info = require_card_info(card)
        if not request.has_keyword(card_info):
            return self._client_error(request.keyword_error(card_info))
        if not request.can_cast(card_info):
            return self._client_error(request.timing_error)
        if request.prepay is not None:
            prepay_err = request.prepay(card, card_info)
            if prepay_err is not None:
                return self._client_error(prepay_err)
        mana_needed, life_cost = split_mana_cost(request.mana_cost(card_info))
        mana_err = self._tap_mana_or_error(request.player_idx, mana_needed)
        if mana_err is not None:
            return mana_err
        detail = (
            request.log_detail(card_info)
            if callable(request.log_detail)
            else request.log_detail
        )
        return self._complete_announce_cast(
            AnnounceCastCompletion(
                card=card,
                card_info=card_info,
                player_idx=request.player_idx,
                target_uid_str=target_uid_str,
                target_player_idx=target_player_idx,
                context=SpellCastContext(
                    alternate=request.alternate,
                    from_graveyard=True,
                ),
                log_action=request.log_action,
                log_detail=detail,
                auto_resolve=auto_resolve,
                life_cost=life_cost,
            ),
        )
