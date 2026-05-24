"""Offspring: ETB creates a token copy (simplified)."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords._token_factory import enter_token_from_blueprint
from engine.cards.oracle_parse import TokenBlueprint
from engine.core.game_object import Permanent
from engine.core.zones import ZoneManager


def has_offspring(perm: Permanent) -> bool:
    """Return True when the permanent has offspring."""
    return has_keyword(perm, 'Offspring')


def apply_offspring_etb(zones: ZoneManager, permanent: Permanent) -> str | None:
    """Create a token copy when offspring is present (simplified)."""
    if not has_offspring(permanent):
        return None
    power = str(permanent.card_info.numeric_power if permanent.card_info else 1)
    toughness = str(
        permanent.card_info.numeric_toughness if permanent.card_info else 1
    )
    blueprint = TokenBlueprint(
        name=f"{permanent.name} Token",
        type_line=permanent.type_line,
        power=power,
        toughness=toughness,
        colors=[],
        oracle_text='',
    )
    enter_token_from_blueprint(
        zones,
        permanent.controller_idx,
        blueprint,
        cause='offspring',
    )
    return f"offspring token for {permanent.name}"
