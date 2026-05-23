"""Resolve ability-word triggered clauses (draw, damage, tokens)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.cards.oracle_parse import (
    parse_damage,
    parse_draw,
    parse_life_gain,
    parse_token_blueprint,
)
from engine.abilities.keywords._token_factory import enter_token_from_blueprint
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Effect, GameObject, TriggeredAbilityOnStack
if TYPE_CHECKING:
    from engine.core.game_state import GameState


class AbilityWordEffect(Effect):
    """Apply a parsed oracle clause when an ability-word trigger resolves."""

    def __init__(self, clause: str) -> None:
        self.clause = clause

    def resolve(self, game: GameState, source: GameObject) -> str:
        """Draw, deal damage, gain life, or create a token from the clause."""
        if not isinstance(source, TriggeredAbilityOnStack):
            return ''
        permanent = game.zones.find_permanent(source.source_permanent_id)
        if permanent is None:
            return ''
        controller = permanent.controller_idx
        parts: list[str] = []

        draw_count = parse_draw(self.clause)
        if draw_count > 0:
            drawn = []
            for _ in range(draw_count):
                card = game.zones.draw(controller)
                if card is not None:
                    drawn.append(card)
            parts.append(f"drew {len(drawn)} card(s)")

        damage = parse_damage(self.clause)
        if damage > 0:
            opponent = 1 - controller
            game.players[opponent].life -= damage
            game.mark_player_was_dealt_damage(opponent)
            parts.append(f"dealt {damage} damage")

        life = parse_life_gain(self.clause)
        if life > 0:
            game.gain_life(controller, life, source_permanent_id=permanent.obj_id)
            parts.append(f"gained {life} life")

        blueprint = parse_token_blueprint(self.clause)
        if blueprint is not None:
            name = enter_token_from_blueprint(
                game.zones,
                controller,
                blueprint,
                cause='ability_word',
            )
            parts.append(f"created {name}")

        return ', '.join(parts) if parts else 'triggered'

    def describe(self) -> str:
        """Return a short description for logs."""
        return f"Ability word: {self.clause[:40]}"


class ProwessEffect(Effect):
    """Put a +1/+1 counter on the source permanent (Monastery Swiftspear-style)."""

    def resolve(self, game: GameState, source: GameObject) -> str:
        """Apply one +1/+1 counter to the prowess source."""
        if not isinstance(source, TriggeredAbilityOnStack):
            return ''
        permanent = game.zones.find_permanent(source.source_permanent_id)
        if permanent is None:
            return ''
        put_plus_counters(permanent, 1)
        return f"{permanent.name} gets +1/+1 from Prowess"

    def describe(self) -> str:
        """Return a short description for logs."""
        return "Prowess (+1/+1)"
