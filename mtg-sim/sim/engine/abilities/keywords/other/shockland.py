"""Shocklands and other lands with pay-life-or-enter-tapped ETB."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.core.game_object import Permanent

SHOCKLAND_LIFE_COST = 2


def has_shockland_etb(card: CardInfo) -> bool:
    """Return True when the land may pay 2 life to enter untapped."""
    if not card.is_land:
        return False
    oracle = (card.oracle_text or '').lower()
    return (
        'you may pay 2 life' in oracle
        and 'enters the battlefield tapped' in oracle
    )


def apply_shockland_etb(
    permanent: Permanent,
    card: CardInfo,
    *,
    pay_life: bool,
    player_life: int,
) -> tuple[str | None, int]:
    """Tap the land or pay 2 life when a shockland enters the battlefield."""
    if not has_shockland_etb(card):
        return None, player_life
    if pay_life:
        if player_life <= SHOCKLAND_LIFE_COST:
            permanent.tapped = True
            return f"{card.name} enters tapped (not enough life)", player_life
        permanent.tapped = False
        new_life = player_life - SHOCKLAND_LIFE_COST
        return f"{card.name} enters untapped (paid {SHOCKLAND_LIFE_COST} life)", new_life
    permanent.tapped = True
    return f"{card.name} enters tapped", player_life
