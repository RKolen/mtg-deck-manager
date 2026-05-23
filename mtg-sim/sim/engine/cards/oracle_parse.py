"""
Oracle text parsing utilities for the MTG rules engine.

These are pure functions that extract structured data from Scryfall oracle
text. They are intentionally simple regex-based helpers used until Phase G
replaces them with fully structured Effect objects.

Ported from game_engine.py and extended with token blueprint parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from engine.abilities.keywords.other.affinity import affinity_reduction

if TYPE_CHECKING:
    from deck_registry import CardInfo
    from engine.core.zones import ZoneManager

_WORD_TO_INT = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4}

_CATEGORY_CHECKS: list[tuple[str, str]] = [
    ("burn",    r"deals?.*damage"),
    ("pump",    r"\+\d/\+\d|gets? \+"),
    ("removal", r"destroy|exile"),
    ("draw",    r"draw.*card"),
    ("aura",    r"enchant "),
]

_COLOR_WORDS = frozenset({"white", "blue", "black", "red", "green", "colorless"})


@dataclass
class TokenBlueprint:
    """Template for creating a token permanent."""

    name: str
    type_line: str
    power: str
    toughness: str
    colors: list[str] = field(default_factory=list)
    oracle_text: str = ""


def parse_damage(text: str) -> int:
    """Return the first explicit numeric damage value found, or 0."""
    m = re.search(r"deals? (\d+) damage", text, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def parse_pump(text: str) -> tuple[int, int]:
    """Return the (power, toughness) bonus from a pump or base-P/T effect."""
    m = re.search(r"gets? \+(\d+)/\+(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"base power and toughness (\d+)/(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def parse_draw(text: str) -> int:
    """Return the number of cards drawn by a draw effect, or 0."""
    m = re.search(r"draw (\w+) card", text, re.IGNORECASE)
    if not m:
        return 0
    word = m.group(1).lower()
    return _WORD_TO_INT.get(word, int(word) if word.isdigit() else 1)


def parse_life_gain(text: str) -> int:
    """Return life gained from a 'gain N life' effect, or 0."""
    m = re.search(r"gain (\d+) life", text, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def parse_token_blueprint(text: str) -> TokenBlueprint | None:
    """Extract a token blueprint from a 'create a N/N COLOR TYPE creature token' clause.

    Returns None if the pattern is not found.
    """
    m = re.search(
        r"create (?:a|an) (\d+)/(\d+) ([\w ]+?) creature token",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    power, toughness, descriptor = m.group(1), m.group(2), m.group(3).strip().lower()
    words = descriptor.split()
    colors = [w.upper()[0] for w in words if w in _COLOR_WORDS and w != "colorless"]
    subtype_words = [w for w in words if w not in _COLOR_WORDS]
    subtype = " ".join(w.title() for w in subtype_words) if subtype_words else descriptor.title()
    return TokenBlueprint(
        name=f"{subtype} Token",
        type_line=f"Creature — {subtype}",
        power=power,
        toughness=toughness,
        colors=colors,
    )


def mana_needed_to_cast(
    card: CardInfo,
    zones: ZoneManager | None = None,
    controller_idx: int = 0,
) -> int:
    """Return untapped lands needed to cast this spell (simplified).

    Phyrexian pips ({W/P} etc.) can each be paid with 2 life instead of
    mana, reducing the minimum mana required by one per pip.
    Affinity for artifacts reduces generic mana when zones are provided.
    """
    if card.is_land:
        return 0
    phyrexian_pips = (card.mana_cost or "").upper().count("/P")
    mana_needed = max(0, int(card.cmc) - phyrexian_pips)
    if zones is not None:
        mana_needed = max(0, mana_needed - affinity_reduction(card, zones, controller_idx))
    return mana_needed


def is_affordable(
    card: CardInfo,
    available_mana: int,
    zones: ZoneManager | None = None,
    controller_idx: int = 0,
) -> bool:
    """True when the player can cast this spell with the given mana available.

    Lands are never castable (they are played, not cast).
    """
    if card.is_land:
        return False
    return available_mana >= mana_needed_to_cast(card, zones, controller_idx)


def spell_category(card: CardInfo) -> str:
    """Classify a card into a broad effect category for simplified resolution.

    This is a temporary heuristic used until Phase G (structured scripting).
    """
    if card.is_land:
        return "land"
    if card.is_creature:
        return "creature"
    text = (card.oracle_text or "").lower()
    for category, pattern in _CATEGORY_CHECKS:
        if re.search(pattern, text):
            return category
    return "spell"
