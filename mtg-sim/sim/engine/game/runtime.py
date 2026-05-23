"""Zone, mana, and logging helpers mixed into InteractiveGame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.cards.oracle_parse import is_affordable
from engine.core.game_object import CardObject, Permanent
from engine.core.game_object import SpellOnStack
from engine.core.game_state import LogEntry
from engine.core.game_object import (
    spell_exiles_from_graveyard_cast,
    spell_is_ephemeral_copy,
    spell_returns_to_hand_on_resolve,
)
from engine.game._hand_card import graveyard_card_or_error, hand_card_or_error
from engine.game.helpers import card_to_client, has_instant_timing, is_land, require_card_info

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
            "playerTotalMana": self._total_mana(0),
            "playerLandPlayed": self.state.players[0].land_played,
            "playerGraveyard": self._graveyard_names(0),
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
        return [
            card_to_client(idx, require_card_info(card), available)
            for idx, card in enumerate(hand)
            if isinstance(card, CardObject) and card.card_info is not None
        ]

    def _battlefield_to_client(self, player_idx: int) -> list[dict]:
        """Serialise a player's battlefield permanents."""
        return [p.to_dict() for p in self._permanents(player_idx)]

    def _graveyard_names(self, player_idx: int) -> list[str]:
        """Return the last few graveyard card names."""
        names: list[str] = []
        for card in self._zones(player_idx).graveyard[-5:]:
            if isinstance(card, CardObject) and card.card_info is not None:
                names.append(card.card_info.name)
        return names

    def _has_castable_instant(self) -> bool:
        """Return whether the player can cast an instant in the current window."""
        return any(
            has_instant_timing(require_card_info(card))
            and is_affordable(
                require_card_info(card),
                self._available_mana(0),
                self.state.zones,
                0,
            )
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
        """Tap untapped lands to pay generic mana."""
        lands = self.state.zones.untapped_lands_of(player_idx)
        if len(lands) < amount:
            return False
        for land in lands[:amount]:
            land.tapped = True
        return True

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
        self.state.zones.player_zones[card.owner_idx].graveyard.append(card)

    def _relocate_resolved_spell(self, spell: SpellOnStack, card: CardObject) -> None:
        """Exile alt-cast spells, return buyback spells to hand, else graveyard."""
        if spell_is_ephemeral_copy(spell):
            return
        if spell_exiles_from_graveyard_cast(spell):
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
            if not self.state.stack.is_empty:
                self.action_pass_priority()
