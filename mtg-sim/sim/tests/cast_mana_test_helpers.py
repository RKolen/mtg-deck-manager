"""Shared announce-cast mana helpers for keyword casting tests."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaTiming,
    _DirectTimingCasts,
    resolve_announce_cast_mana,
)
from engine.game.cast_alt_mode_flags import AltCastModeFlags


def resolve_alt_mode_cast_mana(
    card: CardInfo,
    *,
    warp: bool = False,
    web_slinging: bool = False,
    converted: bool = False,
) -> tuple[int, int]:
    """Resolve announce-cast mana for warp / web-slinging / converted modes."""
    return resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(
            timing=CastManaTiming(
                direct=_DirectTimingCasts(
                    alt_modes=AltCastModeFlags(
                        warp=warp,
                        web_slinging=web_slinging,
                        converted=converted,
                    ),
                ),
            ),
        ),
    )
