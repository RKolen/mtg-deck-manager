"""Squad: pay {N} to create N 1/1 token copies when this creature enters."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords._token_factory import enter_token_from_blueprint
from engine.abilities.keywords.registry import has_registered_keyword
from engine.cards.oracle_parse import TokenBlueprint
from engine.core.game_object import Permanent
from engine.core.zones import ZoneManager

_SQUAD_RE = re.compile(r'squad\s*\{(\w+)\}', re.IGNORECASE)


def has_squad(card: CardInfo) -> bool:
    """Return True when the card has squad."""
    return has_registered_keyword(card.oracle_text, 'Squad') or bool(
        _SQUAD_RE.search(card.oracle_text or '')
    )


def normalize_squad_times(card: CardInfo, squad_times: int) -> int:
    """Clamp squad payments to legal values for this card."""
    if squad_times <= 0 or not has_squad(card) or not card.is_creature:
        return 0
    return squad_times


def squad_extra_mana(card: CardInfo, squad_times: int) -> int:
    """Return additional generic mana owed for squad payments."""
    return normalize_squad_times(card, squad_times)


def apply_squad_on_etb(
    zones: ZoneManager,
    permanent: Permanent,
    squad_times: int,
) -> str | None:
    """Create squad tokens when the creature resolves."""
    card = permanent.card_info
    if card is None or squad_times <= 0:
        return None
    times = normalize_squad_times(card, squad_times)
    if times <= 0:
        return None
    power = str(card.numeric_power if card.numeric_power else 1)
    toughness = str(card.numeric_toughness if card.numeric_toughness else 1)
    blueprint = TokenBlueprint(
        name=f"{card.name} Token",
        type_line=card.type_line,
        power=power,
        toughness=toughness,
        colors=[],
        oracle_text='',
    )
    for _ in range(times):
        enter_token_from_blueprint(
            zones,
            permanent.controller_idx,
            blueprint,
            cause='squad',
        )
    return f"squad {permanent.name} ({times} token(s))"
