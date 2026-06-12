"""Forecast: activate from hand during upkeep (CR 702.36, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword

_FORECAST_RE = re.compile(
    r'forecast\s*[—–-]\s*(.+?)(?:\n|$)',
    re.IGNORECASE,
)


def has_forecast(card: CardInfo) -> bool:
    """Return True when the card has forecast."""
    return has_registered_keyword(card.oracle_text, 'Forecast') or bool(
        _FORECAST_RE.search(card.oracle_text or '')
    )


def can_forecast(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when forecast may be activated from hand (draw step proxy)."""
    return has_forecast(card) and phase == 'draw' and stack_is_empty


def forecast_draws_card(card: CardInfo) -> bool:
    """Return True when the forecast clause draws a card."""
    match = _FORECAST_RE.search(card.oracle_text or '')
    clause = match.group(1).lower() if match is not None else ''
    return 'draw a card' in clause or 'draw two cards' in clause
