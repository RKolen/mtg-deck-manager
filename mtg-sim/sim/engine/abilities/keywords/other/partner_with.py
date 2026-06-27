"""Partner with: deck must include a specific partner commander."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword

_PARTNER_WITH_RE = re.compile(
    r'partner\s+with\s+([^\n(]+)',
    re.IGNORECASE,
)


def has_partner_with(card: CardInfo) -> bool:
    """Return True when the card has Partner with."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Partner with') or bool(
        _PARTNER_WITH_RE.search(text)
    )


def partner_with_name(card: CardInfo) -> str | None:
    """Return the named partner for Partner with."""
    match = _PARTNER_WITH_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return match.group(1).strip()


def validate_partner_with_deck(deck: list[CardInfo]) -> str | None:
    """Return an error when Partner with requirements are not met."""
    partners = [card for card in deck if has_partner_with(card)]
    if not partners:
        return None
    if len(partners) < 2:
        return "Partner with deck must include two partner legendary creatures"
    named = partner_with_name(partners[0])
    if named is not None:
        if not any(named.lower() in card.name.lower() for card in partners[1:]):
            return f"Partner with {named} requires that creature in the deck"
    return None
