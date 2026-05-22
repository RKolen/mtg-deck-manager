"""Create token permanents from blueprints."""

from __future__ import annotations

from engine.cards.oracle_parse import TokenBlueprint
from engine.core.game_object import TokenObject
from engine.core.zones import ZoneManager


def enter_token_from_blueprint(
    zones: ZoneManager,
    controller_idx: int,
    blueprint: TokenBlueprint,
    cause: str = 'token',
) -> str:
    """Create a token on the battlefield and return its display name."""
    token = TokenObject(
        controller_idx=controller_idx,
        owner_idx=controller_idx,
        name=blueprint.name,
        type_line=blueprint.type_line,
        colors=blueprint.colors,
        power=blueprint.power,
        toughness=blueprint.toughness,
        oracle_text=blueprint.oracle_text,
    )
    zones.enter_battlefield(token, controller_idx, cause)
    return blueprint.name
