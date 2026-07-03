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
from typing import TYPE_CHECKING, Literal

from engine.abilities.keywords.other.affinity import affinity_reduction
from engine.abilities.keywords.actions._parse import word_to_int

if TYPE_CHECKING:
    from deck_registry import CardInfo
    from engine.core.zones import ZoneManager

DiscardTarget = Literal['controller', 'target_player', 'each_opponent']

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


def parse_each_opponent_life_loss(text: str) -> int:
    """Return life lost from 'each opponent loses N life', or 0."""
    m = re.search(r"each opponent loses (\d+) life", text, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def parse_discard(text: str) -> tuple[int, DiscardTarget] | None:
    """Return (count, target) for discard effects, or None when absent.

    target is one of: controller, target_player, each_opponent.
    """
    each = re.search(
        r"each opponent discards (?:a|an|one|(\w+|\d+)) cards?",
        text,
        re.IGNORECASE,
    )
    if each is not None:
        count = word_to_int(each.group(1)) if each.group(1) else 1
        return count, 'each_opponent'
    target_player = re.search(
        r"target (?:player|opponent) discards (?:a|an|one|(\w+|\d+)) cards?",
        text,
        re.IGNORECASE,
    )
    if target_player is not None:
        count = word_to_int(target_player.group(1)) if target_player.group(1) else 1
        return count, 'target_player'
    self_discard = re.search(
        r"(?:you )?discards? (?:a|an|one|(\w+|\d+)) cards?",
        text,
        re.IGNORECASE,
    )
    if self_discard is not None:
        count = word_to_int(self_discard.group(1)) if self_discard.group(1) else 1
        return count, 'controller'
    return None


def parse_token_create_count(text: str) -> int:
    """Return how many tokens a create clause makes (0 when none)."""
    if not re.search(r"create ", text, re.IGNORECASE):
        return 0
    numbered = re.search(
        r"create (two|three|four|five|six|seven|eight|nine|ten|\d+)",
        text,
        re.IGNORECASE,
    )
    if numbered is not None:
        return word_to_int(numbered.group(1))
    if re.search(r"create (?:a|an) ", text, re.IGNORECASE):
        return 1
    return 0


def parse_look_at_count(text: str) -> int:
    """Return N from 'look at the top N cards', or 0."""
    match = re.search(r"look at the top (\w+|\d+) cards?", text, re.IGNORECASE)
    if match is None:
        return 0
    return word_to_int(match.group(1))


def parse_delirium_damage(text: str) -> tuple[int, int] | None:
    """Return (base, delirium) damage amounts when oracle has a delirium clause."""
    if 'delirium' not in text.lower():
        return None
    amounts = [int(match.group(1)) for match in re.finditer(r"deals? (\d+) damage", text, re.I)]
    if len(amounts) >= 2:
        return amounts[0], amounts[1]
    if len(amounts) == 1:
        return amounts[0], amounts[0]
    return None


def parse_modal_clauses(text: str) -> list[str] | None:
    """Split a 'Choose one' spell into bullet clause oracle fragments."""
    if not re.search(r"choose (?:one|two|up to one|any number)", text, re.IGNORECASE):
        return None
    if '•' in text or '\u2022' in text:
        parts = re.split(r"[•\u2022]", text)
        clauses = [part.strip().strip('—–-').strip() for part in parts[1:] if part.strip()]
        if len(clauses) >= 2:
            return clauses
    lines = text.splitlines()
    clauses: list[str] = []
    past_header = False
    for line in lines:
        if re.search(r"choose (?:one|two|up to one)", line, re.IGNORECASE):
            past_header = True
            continue
        if not past_header:
            continue
        stripped = re.sub(r"^[\s\-–—]+\s*", "", line.strip())
        if stripped:
            clauses.append(stripped)
    return clauses if len(clauses) >= 2 else None


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
    """True when the player can cast this spell with available mana sources.

    Lands are never castable (they are played, not cast). When ``zones`` is
    provided, colored mana requirements are checked against land colors.
    """
    if card.is_land:
        return False
    land_slots = mana_needed_to_cast(card, zones, controller_idx)
    if zones is not None:
        from engine.game.mana_payment import can_pay_cast_mana  # pylint: disable=import-outside-toplevel

        return can_pay_cast_mana(zones, controller_idx, card, land_slots)
    return available_mana >= land_slots


def spell_category(card: CardInfo) -> str:
    """Classify a card into a broad effect category for simplified resolution.

    This is a temporary heuristic used until Phase G (structured scripting).
    Scripted cards use per-deck JSON caches synced at game start (Phase G).
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
