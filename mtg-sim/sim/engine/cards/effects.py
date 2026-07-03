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
from engine.rules.modifiers import add_until_eot_pt_modifier, add_until_eot_set_pt_modifier

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
        from engine.game.helpers import target_player as target_player_from_targets  # pylint: disable=import-outside-toplevel
        from engine.game.helpers import target_uid  # pylint: disable=import-outside-toplevel

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
class PumpUntilEOT(CardEffect):
    """Grant +P/+T until end of turn to a targeted creature."""

    power: int
    toughness: int

    def apply(self, ctx: CardEffectContext) -> str:
        """Apply a until-end-of-turn power/toughness bonus."""
        target = ctx.target_creature()
        if target is None:
            return 'no valid target'
        add_until_eot_pt_modifier(
            target,
            power_delta=self.power,
            toughness_delta=self.toughness,
            source_obj_id=ctx.source.obj_id,
        )
        return f"pumped {target.name} (+{self.power}/+{self.toughness})"


@dataclass(frozen=True)
class SetPowerToughnessUntilEOT(CardEffect):
    """Set base power and toughness until end of turn (layer 7b)."""

    power: int
    toughness: int

    def apply(self, ctx: CardEffectContext) -> str:
        """Set P/T on the targeted creature until end of turn."""
        target = ctx.target_creature()
        if target is None:
            return 'no valid target'
        add_until_eot_set_pt_modifier(
            target,
            self.power,
            self.toughness,
            source_obj_id=ctx.source.obj_id,
        )
        return f"set {target.name} to {self.power}/{self.toughness}"


@dataclass(frozen=True)
class DestroyIfMaxManaValue(CardEffect):
    """Destroy target creature when its mana value is at most max_mv."""

    max_mv: int

    def apply(self, ctx: CardEffectContext) -> str:
        """Destroy the target if its mana value is within range."""
        target = ctx.target_creature()
        if target is None:
            return 'no valid target'
        mana_value = 99
        if isinstance(target.source, CardObject) and target.source.card_info is not None:
            mana_value = int(target.source.card_info.cmc)
        if mana_value > self.max_mv:
            return f"{target.name} not destroyed (MV {mana_value})"
        ctx.game.zones.leave_battlefield(target, Zone.GRAVEYARD, 'destroy', ctx.game)
        return f"destroyed {target.name}"


@dataclass(frozen=True)
class DrainLife(CardEffect):
    """Target opponent loses life and the controller gains the same amount."""

    amount: int
    target: PlayerTarget = 'target_player'

    def apply(self, ctx: CardEffectContext) -> str:
        """Drain life from the chosen player."""
        if self.amount <= 0:
            return ''
        victim = ctx.resolve_player(self.target)
        ctx.game.players[victim].life -= self.amount
        ctx.game.gain_life(ctx.controller_idx, self.amount)
        return f"drained {self.amount} from P{victim + 1}"


@dataclass(frozen=True)
class TreasureHunt(CardEffect):
    """Reveal from library until a nonland, then put revealed cards into hand."""

    def apply(self, ctx: CardEffectContext) -> str:
        """Run the Treasure Hunt reveal loop (lands included in hand)."""
        lib = ctx.game.zones.player_zones[ctx.controller_idx].library
        revealed: list[CardObject] = []
        while lib:
            card = lib.pop(0)
            if not isinstance(card, CardObject):
                continue
            revealed.append(card)
            if card.card_info is not None and not card.card_info.is_land:
                break
        hand = ctx.game.zones.player_zones[ctx.controller_idx].hand
        for card in revealed:
            hand.append(card)
        return f"treasure hunt put {len(revealed)} card(s) in hand"


@dataclass(frozen=True)
class NoEffect(CardEffect):
    """Placeholder for modes or branches not yet modeled."""

    label: str = ''

    def apply(self, ctx: CardEffectContext) -> str:
        """Return an empty log fragment."""
        _ = ctx
        return ''


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
