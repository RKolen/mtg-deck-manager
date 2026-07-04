"""Zone, mana, and logging helpers mixed into InteractiveGame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.cards.oracle_parse import is_affordable
from engine.core.game_object import CardObject, Permanent, Target
from engine.core.mana import ManaCost
from engine.core.game_object import SpellOnStack
from engine.core.game_state import LogEntry
from engine.abilities.activated.core import activation_mana_cost
from engine.core.zones import PutCardInZoneRequest, Zone
from engine.rules.mana_payment import pay_cast_mana, pay_mana_cost
from engine.core.game_object import (
    spell_exiles_from_graveyard_cast,
    spell_is_ephemeral_copy,
    spell_returns_to_hand_on_resolve,
)
from engine.game._hand_card import (
    exile_card_or_error,
    graveyard_card_or_error,
    hand_card_or_error,
)
from engine.abilities.keywords.casting.paradigm import (
    exile_for_paradigm,
    should_exile_for_paradigm,
)
from engine.abilities.keywords.casting.rebound import (
    exile_for_rebound,
    should_exile_for_rebound,
)
from engine.game.helpers import (
    HandCastContext,
    SpellCastContext,
    card_to_client,
    has_instant_timing,
    is_land,
    require_card_info,
    spell_on_stack_from_context,
    targets_from_request,
)
from engine.game.cast_flow import (
    AnnounceCastCompletion,
    ExileCastRequest,
    GraveyardCastRequest,
    _CastLog,
    _TargetRef,
    not_enough_mana_message,
    split_mana_cost,
)
from engine.game.cast_modifiers import apply_post_cast_modifiers
from engine.game.cast_context import _HandCastExtras

if TYPE_CHECKING:
    from engine.core.game_state import GameState


class GameRuntimeMixin:
    """Shared runtime utilities for interactive play."""

    if TYPE_CHECKING:
        mulligans_taken: int

        def _available_actions(self) -> list[str]:
            """Return action names available to the player in the current phase."""
            return []

        def action_pass_priority(self) -> dict:
            """Pass priority once and return the updated client state."""
            return {}

    state: GameState
    phase: str
    pending_attackers: list[str]
    pending_opp_attackers: list[str]
    pending_blockers: dict[str, str]

    @property
    def turn(self) -> int:
        """Current turn number for the legacy client contract."""
        return self.state.turn.context.turn_number

    @property
    def winner(self) -> int | None:
        """Winning player index, or None while the game is active."""
        return self.state.winner

    def to_client(self) -> dict:
        """Serialise game state using the existing frontend payload shape."""
        return {
            "gameId": self.state.game_id,
            "turn": self.turn,
            "phase": self.phase,
            "winner": self.winner,
            "playerHand": self._hand_to_client(0),
            "playerBattlefield": self._battlefield_to_client(0),
            "playerLife": self.state.players[0].life,
            "playerMana": self._available_mana(0),
            "playerManaPool": self.state.players[0].mana_pool.to_client(),
            "playerTotalMana": self._total_mana(0),
            "playerLandPlayed": self.state.players[0].land_played,
            "playerGraveyard": self._graveyard_names(0),
            "playerGraveyardCards": self._graveyard_cards(0),
            "playerExileCards": self._exile_cards(0),
            "opponentHandCount": len(self._zones(1).hand),
            "opponentBattlefield": self._battlefield_to_client(1),
            "opponentLife": self.state.players[1].life,
            "opponentMana": self._total_mana(1),
            "opponentGraveyard": self._graveyard_names(1),
            "log": self._log_to_client(limit=20),
            "pendingAttackers": self.pending_attackers,
            "opponentAttackers": [
                p.to_dict() for p in self._permanents(1)
                if str(p.obj_id) in self.pending_opp_attackers
            ],
            "pendingBlockers": self.pending_blockers,
            "stack": self.state.stack.to_client(),
            "availableActions": self._available_actions(),
        }

    def _hand_to_client(self, player_idx: int) -> list[dict]:
        """Serialise a player's hand for the existing client contract."""
        available = self._available_mana(player_idx)
        hand = self._zones(player_idx).hand
        stack_empty = self.state.stack.is_empty
        return [
            card_to_client(
                idx,
                require_card_info(card),
                available,
                HandCastContext(
                    phase=self.phase,
                    stack_is_empty=stack_empty,
                    zones=self.state.zones,
                    controller_idx=player_idx,
                    game=self.state,
                ),
            )
            for idx, card in enumerate(hand)
            if isinstance(card, CardObject) and card.card_info is not None
        ]

    def _battlefield_to_client(self, player_idx: int) -> list[dict]:
        """Serialise a player's battlefield permanents."""
        return [p.to_dict() for p in self._permanents(player_idx)]

    def _graveyard_names(self, player_idx: int) -> list[str]:
        """Return the last few graveyard card names."""
        return [entry["name"] for entry in self._graveyard_cards(player_idx)[-5:]]

    def _graveyard_cards(self, player_idx: int) -> list[dict]:
        """Return graveyard cards with indices for client graveyard actions."""
        cards: list[dict] = []
        for idx, card in enumerate(self._zones(player_idx).graveyard):
            if isinstance(card, CardObject) and card.card_info is not None:
                cards.append({"idx": idx, "name": card.card_info.name})
        return cards

    def _exile_cards(self, player_idx: int) -> list[dict]:
        """Return exiled cards with indices for foretell/plot casts."""
        cards: list[dict] = []
        for idx, card in enumerate(self._zones(player_idx).exile):
            if isinstance(card, CardObject) and card.card_info is not None:
                entry: dict = {"idx": idx, "name": card.card_info.name}
                if card.exiled_cast_mode:
                    entry["castMode"] = card.exiled_cast_mode
                cards.append(entry)
        return cards

    def _is_card_castable(self, card: CardObject) -> bool:
        """Return whether the player can currently afford to cast the card."""
        return is_affordable(
            require_card_info(card),
            self._available_mana(0),
            self.state.zones,
            0,
        )

    def _has_castable_instant(self) -> bool:
        """Return whether the player can cast an instant in the current window."""
        return any(
            has_instant_timing(require_card_info(card)) and self._is_card_castable(card)
            for card in self._zones(0).hand
            if isinstance(card, CardObject) and not is_land(card)
        )

    def _log_to_client(self, limit: int | None = None) -> list[dict]:
        """Serialise game log entries."""
        entries = self.state.log[-limit:] if limit is not None else self.state.log
        return [
            {"turn": e.turn, "actor": e.actor, "action": e.action, "detail": e.detail}
            for e in entries
        ]

    def _draw_cards(self, player_idx: int, count: int) -> list[CardObject]:
        """Draw up to count cards for a player."""
        drawn: list[CardObject] = []
        for _ in range(count):
            card = self.state.zones.draw(player_idx)
            if card is not None:
                drawn.append(card)
        return drawn

    def _bottom_mulligan_cards(self, player_idx: int) -> list[CardObject]:
        """Put one card per mulligan taken on the bottom of that player's library."""
        count = min(self.mulligans_taken, len(self._zones(player_idx).hand))
        if count <= 0:
            return []
        hand = self._zones(player_idx).hand
        bottomed = [c for c in hand[-count:] if isinstance(c, CardObject)]
        del hand[-count:]
        self._zones(player_idx).library.extend(bottomed)
        return bottomed

    def _tap_lands_for_mana(self, player_idx: int, amount: int) -> bool:
        """Tap untapped lands to pay generic mana (activated abilities, fallbacks)."""
        lands = self.state.zones.untapped_lands_of(player_idx)
        if len(lands) < amount:
            return False
        for land in lands[:amount]:
            land.tapped = True
        return True

    def _tap_mana_for_spell(self, player_idx: int, card_info: CardInfo, land_slots: int) -> bool:
        """Pay a spell cost using the mana pool and land colors."""
        return pay_cast_mana(self.state, player_idx, card_info, land_slots)

    def _pay_mana_for_action(
        self,
        player_idx: int,
        *,
        cost: ManaCost | None = None,
        cost_text: str | None = None,
        mana_needed: int = 0,
    ) -> bool:
        """Pay a spell or activation mana cost using the pool and land colors."""
        resolved = cost
        if cost_text is not None:
            resolved = activation_mana_cost(cost_text)
        elif resolved is None and mana_needed > 0:
            resolved = ManaCost(generic=mana_needed)
        if resolved is None or resolved.mana_value == 0:
            return True
        return pay_mana_cost(self.state, player_idx, resolved)

    def _empty_mana_pools(self) -> None:
        """Drain floating mana from each player (CR 106.4, simplified)."""
        for player in self.state.players:
            player.mana_pool.empty()

    def _available_mana(self, player_idx: int) -> int:
        return len(self.state.zones.untapped_lands_of(player_idx))

    def _total_mana(self, player_idx: int) -> int:
        return len(self.state.zones.lands_of(player_idx))

    def _permanents(self, player_idx: int) -> list[Permanent]:
        return self.state.zones.permanents_of(player_idx)

    def _zones(self, player_idx: int):
        return self.state.zones.player_zones[player_idx]

    def _client_error(self, message: str) -> dict:
        """Return a client payload with an error message."""
        return {**self.to_client(), "error": message}

    def _hand_card_checked(
        self,
        player_idx: int,
        hand_idx: int,
    ) -> tuple[CardObject | None, dict | None]:
        """Return (card, error_dict); error_dict is set when lookup fails."""
        card, _info, err = hand_card_or_error(self.state.zones, player_idx, hand_idx)
        if err:
            return None, self._client_error(err)
        return card, None

    def _graveyard_card_checked(
        self,
        player_idx: int,
        graveyard_idx: int,
    ) -> tuple[CardObject | None, dict | None]:
        """Return (card, error_dict); error_dict is set when lookup fails."""
        card, _info, err = graveyard_card_or_error(
            self.state.zones,
            player_idx,
            graveyard_idx,
        )
        if err:
            return None, self._client_error(err)
        return card, None

    def _load_graveyard_card(
        self,
        player_idx: int,
        graveyard_idx: int,
    ) -> tuple[CardObject | None, CardInfo | None, dict | None]:
        """Return (card, card_info, None) or (None, None, error_dict)."""
        card, err = self._graveyard_card_checked(player_idx, graveyard_idx)
        if err is not None:
            return None, None, err
        assert card is not None
        return card, require_card_info(card), None

    def _exile_card_checked(
        self,
        player_idx: int,
        exile_idx: int,
    ) -> tuple[CardObject | None, CardInfo | None, dict | None]:
        """Return (card, card_info, error_dict); error_dict is set when lookup fails."""
        card, card_info, err = exile_card_or_error(
            self.state.zones,
            player_idx,
            exile_idx,
        )
        if err:
            return None, None, self._client_error(err)
        return card, card_info, None

    def _load_hand_card(
        self,
        player_idx: int,
        hand_idx: int,
    ) -> tuple[CardObject | None, CardInfo | None, dict | None]:
        """Return (card, card_info, None) or (None, None, error_dict)."""
        card, err = self._hand_card_checked(player_idx, hand_idx)
        if err is not None:
            return None, None, err
        assert card is not None
        return card, require_card_info(card), None

    def _find_permanent(self, uid: str | None) -> Permanent | None:
        if uid is None:
            return None
        try:
            return self.state.zones.find_permanent(int(uid))
        except ValueError:
            return None

    def _move_card_to_graveyard(self, card: CardObject) -> None:
        self.state.zones.put_card_in_zone(PutCardInZoneRequest(
            card=card,
            to_zone=Zone.GRAVEYARD,
            player_idx=card.owner_idx,
            cause='spell',
            game=self.state,
            from_zone=Zone.STACK,
        ))

    def _relocate_resolved_spell(self, spell: SpellOnStack, card: CardObject) -> None:
        """Exile alt-cast spells, return buyback spells to hand, else graveyard."""
        if spell_is_ephemeral_copy(spell):
            return
        card_info = card.card_info
        if (
            card_info is not None
            and should_exile_for_paradigm(spell, card_info)
        ):
            exile_for_paradigm(self.state.zones, card, self.state)
        elif (
            card_info is not None
            and should_exile_for_rebound(spell, card_info)
        ):
            exile_for_rebound(self.state.zones, card)
        elif spell_exiles_from_graveyard_cast(spell):
            self.state.zones.player_zones[card.owner_idx].exile.append(card)
        elif spell_returns_to_hand_on_resolve(spell):
            self._zones(card.owner_idx).hand.append(card)
        else:
            self._move_card_to_graveyard(card)

    def _log(self, actor: str, action: str, detail: str = "") -> None:
        self.state.log.append(LogEntry(
            turn=self.turn,
            actor=actor,
            action=action,
            detail=detail,
        ))

    def deal_opening_hands(self) -> None:
        """Draw opening hands for both players."""
        self._draw_cards(0, 7)
        self._draw_cards(1, 7)

    def _auto_pass_stack(self) -> None:
        """Auto-pass both players until the stack is empty."""
        while not self.state.stack.is_empty:
            self.action_pass_priority()

    def _put_spell_on_stack(
        self,
        player_idx: int,
        card: CardObject,
        target_ref: _TargetRef,
        context: SpellCastContext | None = None,
    ) -> list[Target]:
        """Move a cast spell onto the stack."""
        opts = context or SpellCastContext()
        targets = targets_from_request(target_ref.target_uid_str, target_ref.target_player_idx)
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

    def _tap_mana_or_error(
        self,
        player_idx: int,
        mana_needed: int,
        card_info: CardInfo | None = None,
    ) -> dict | None:
        """Tap lands for mana; return a client error dict when payment fails."""
        if card_info is not None and self._tap_mana_for_spell(player_idx, card_info, mana_needed):
            return None
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
            log_opts=_CastLog(
                log_action="cast",
                log_detail=request.log_detail,
                auto_resolve=request.auto_resolve,
                life_cost=request.life_cost,
            ),
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
            _TargetRef(completion.target_uid_str, completion.target_player_idx),
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
        target_ref: _TargetRef,
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
        mana_err = self._tap_mana_or_error(
            request.player_idx,
            mana_needed,
            card_info,
        )
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
                target_uid_str=target_ref.target_uid_str,
                target_player_idx=target_ref.target_player_idx,
                context=SpellCastContext(
                    alternate=request.alternate,
                    from_graveyard=True,
                    extras=_HandCastExtras(mayhem=request.log_action == 'mayhem'),
                ),
                log_opts=_CastLog(
                    log_action=request.log_action,
                    log_detail=detail,
                    auto_resolve=auto_resolve,
                    life_cost=life_cost,
                ),
            ),
        )
