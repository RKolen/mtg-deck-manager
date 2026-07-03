"""Structured card effects (Phase G / E13).

Card scripts compose ``CardEffect`` objects instead of relying on oracle regex.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from engine.abilities.keywords.actions.library import mill_cards, scry_cards
from engine.abilities.keywords.actions.targets import find_creature_by_uid
from engine.core.game_object import CardObject, Permanent, SpellOnStack
from engine.core.zones import Zone
from engine.game.helpers import target_player as target_player_from_targets
from engine.game.helpers import target_uid

if TYPE_CHECKING:
    from engine.core.game_state import GameState

PlayerTarget = Literal['controller', 'opponent', 'target_player']
MillTarget = Literal['controller', 'opponent', 'each', 'target_player']
DrawFn = Callable[[int, int], list[CardObject]]


class CardEffect(ABC):  # pylint: disable=too-few-public-methods
    """A single structured effect applied during spell or ability resolution."""

    @abstractmethod
    def apply(self, ctx: CardEffectContext) -> str:
        """Apply the effect and return a short resolution log fragment."""


@dataclass
class CardEffectContext:
    """Runtime inputs for applying scripted card effects."""

    game: GameState
    controller_idx: int
    source: CardObject
    target_player_idx: int | None = None
    target_creature_uid: str | None = None
    selected_mode: int | None = None
    draw_fn: DrawFn | None = None

    @classmethod
    def from_spell(
        cls,
        game: GameState,
        spell: SpellOnStack,
        draw_fn: DrawFn | None = None,
    ) -> CardEffectContext:
        """Build context from a resolving spell on the stack."""
        card = spell.source
        if card is None:
            raise ValueError('spell has no source card')
        mode_idx = spell.modes[0] if spell.modes else None
        return cls(
            game=game,
            controller_idx=spell.controller_idx,
            source=card,
            target_player_idx=target_player_from_targets(spell.targets),
            target_creature_uid=target_uid(spell.targets),
            selected_mode=mode_idx,
            draw_fn=draw_fn,
        )

    def target_creature(self) -> Permanent | None:
        """Return the targeted creature permanent, if any."""
        return find_creature_by_uid(self.game.zones, self.target_creature_uid)

    def resolve_player(self, target: PlayerTarget) -> int:
        """Map a player target specifier to a player index."""
        if target == 'controller':
            return self.controller_idx
        if target == 'opponent':
            return 1 - self.controller_idx
        if self.target_player_idx is not None:
            return self.target_player_idx
        return 1 - self.controller_idx

    def draw_cards(self, count: int) -> list[CardObject]:
        """Draw cards for the controller using the runtime draw hook when set."""
        if count <= 0:
            return []
        if self.draw_fn is not None:
            return self.draw_fn(self.controller_idx, count)
        drawn: list[CardObject] = []
        for _ in range(count):
            card = self.game.zones.draw(self.controller_idx)
            if card is None:
                break
            drawn.append(card)
        return drawn


@dataclass(frozen=True)
class Mill(CardEffect):
    """Move the top N cards of a library into the graveyard."""

    count: int
    target: MillTarget = 'controller'

    def apply(self, ctx: CardEffectContext) -> str:
        """Mill cards for one or both players."""
        if self.target == 'each':
            parts = []
            for idx in (0, 1):
                milled = mill_cards(ctx.game.zones, idx, self.count, ctx.game)
                parts.append(f"P{idx + 1} milled {len(milled)}")
            return '; '.join(parts)
        if self.target == 'controller':
            player_idx = ctx.controller_idx
        elif self.target == 'opponent':
            player_idx = ctx.resolve_player('opponent')
        else:
            player_idx = ctx.resolve_player('target_player')
        milled = mill_cards(ctx.game.zones, player_idx, self.count, ctx.game)
        return f"milled {len(milled)} (P{player_idx + 1})"


@dataclass(frozen=True)
class DrawCards(CardEffect):
    """Draw cards for the spell's controller."""

    count: int

    def apply(self, ctx: CardEffectContext) -> str:
        """Draw the configured number of cards."""
        drawn = ctx.draw_cards(self.count)
        return f"drew {len(drawn)} card(s)"


@dataclass(frozen=True)
class GainLife(CardEffect):
    """Gain life for the controller."""

    amount: int

    def apply(self, ctx: CardEffectContext) -> str:
        """Increase the controller's life total."""
        ctx.game.gain_life(ctx.controller_idx, self.amount)
        return f"gained {self.amount} life"


@dataclass(frozen=True)
class LoseLife(CardEffect):
    """Lose life for the controller."""

    amount: int

    def apply(self, ctx: CardEffectContext) -> str:
        """Decrease the controller's life total."""
        ctx.game.players[ctx.controller_idx].life -= self.amount
        return f"lost {self.amount} life"


@dataclass(frozen=True)
class DealDamageToPlayer(CardEffect):
    """Deal damage to a player."""

    amount: int
    target: PlayerTarget = 'opponent'

    def apply(self, ctx: CardEffectContext) -> str:
        """Deal damage to the chosen player."""
        if self.amount <= 0:
            return ''
        victim = ctx.resolve_player(self.target)
        ctx.game.players[victim].life -= self.amount
        ctx.game.mark_player_was_dealt_damage(victim)
        return f"dealt {self.amount} to P{victim + 1}"


@dataclass(frozen=True)
class DealDamage(CardEffect):
    """Deal damage to a targeted creature, else to a player."""

    amount: int
    player_target: PlayerTarget = 'opponent'

    def apply(self, ctx: CardEffectContext) -> str:
        """Deal damage to the spell's creature target or default player."""
        if self.amount <= 0:
            return ''
        target = ctx.target_creature()
        if target is not None:
            target.damage_marked += self.amount
            ctx.game.check_sbas()
            return f"dealt {self.amount} to {target.name}"
        victim = ctx.resolve_player(self.player_target)
        ctx.game.players[victim].life -= self.amount
        ctx.game.mark_player_was_dealt_damage(victim)
        return f"dealt {self.amount} to P{victim + 1}"


@dataclass(frozen=True)
class DestroyPermanent(CardEffect):
    """Destroy target creature."""

    def apply(self, ctx: CardEffectContext) -> str:
        """Destroy the targeted creature."""
        target = ctx.target_creature()
        if target is None:
            return 'no valid target'
        ctx.game.zones.leave_battlefield(target, Zone.GRAVEYARD, 'destroy', ctx.game)
        return f"destroyed {target.name}"


@dataclass(frozen=True)
class ExilePermanent(CardEffect):
    """Exile target creature."""

    def apply(self, ctx: CardEffectContext) -> str:
        """Exile the targeted creature."""
        target = ctx.target_creature()
        if target is None:
            return 'no valid target'
        ctx.game.zones.leave_battlefield(target, Zone.EXILE, 'exile', ctx.game)
        return f"exiled {target.name}"


@dataclass(frozen=True)
class Modal(CardEffect):
    """Resolve exactly one mode chosen when the spell was cast."""

    modes: tuple[CardEffect, ...]

    def apply(self, ctx: CardEffectContext) -> str:
        """Apply the selected mode effect."""
        idx = ctx.selected_mode if ctx.selected_mode is not None else 0
        if idx < 0 or idx >= len(self.modes):
            return ''
        return self.modes[idx].apply(ctx)


@dataclass(frozen=True)
class Scry(CardEffect):
    """Look at the top N cards and optionally put some on the bottom."""

    count: int
    bottom_indices: tuple[int, ...] = ()

    def apply(self, ctx: CardEffectContext) -> str:
        """Reorder the top of the controller's library."""
        bottomed = scry_cards(
            ctx.game.zones,
            ctx.controller_idx,
            self.count,
            self.bottom_indices,
        )
        return f"scry {self.count} (put {bottomed} on bottom)"


@dataclass(frozen=True)
class EffectList(CardEffect):
    """Apply a sequence of effects in order."""

    effects: tuple[CardEffect, ...]

    def apply(self, ctx: CardEffectContext) -> str:
        """Run each child effect and join the log fragments."""
        parts = [effect.apply(ctx) for effect in self.effects]
        return '; '.join(part for part in parts if part)


@dataclass(frozen=True)
class ConditionalEffect(CardEffect):
    """Apply one branch depending on a predicate."""

    condition: Callable[[CardEffectContext], bool]
    when_true: CardEffect
    when_false: CardEffect | None = None

    def apply(self, ctx: CardEffectContext) -> str:
        """Evaluate the predicate and apply the matching branch."""
        branch = self.when_true if self.condition(ctx) else self.when_false
        if branch is None:
            return ''
        return branch.apply(ctx)
