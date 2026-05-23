"""Token-creation effect used by ability-word trigger registration."""

from __future__ import annotations

from engine.cards.oracle_parse import TokenBlueprint
from engine.core.game_object import (
    Effect,
    GameObject,
    TokenObject,
    TriggeredAbilityOnStack,
)
from engine.core.game_state import GameState


class CreateTokenEffect(Effect):
    """Effect that creates a token from a parsed token blueprint."""

    def __init__(self, blueprint: TokenBlueprint) -> None:
        self.blueprint = blueprint

    def resolve(self, game: GameState, source: GameObject) -> str:
        """Create the token controlled by the source permanent's controller."""
        if not isinstance(source, TriggeredAbilityOnStack):
            return ""
        source_permanent = game.zones.find_permanent(source.source_permanent_id)
        if source_permanent is None:
            return ""
        token = TokenObject(
            controller_idx=source_permanent.controller_idx,
            owner_idx=source_permanent.controller_idx,
            name=self.blueprint.name,
            type_line=self.blueprint.type_line,
            colors=self.blueprint.colors,
            power=self.blueprint.power,
            toughness=self.blueprint.toughness,
            oracle_text=self.blueprint.oracle_text,
        )
        game.zones.enter_battlefield(token, source_permanent.controller_idx, "heroic")
        return f"{source_permanent.name} created {self.blueprint.name}"

    def describe(self) -> str:
        """Return a short description for logs and debugging."""
        return f"Create {self.blueprint.name}"
