"""Disguise: cast face-down 2/2; turn face up for disguise cost (like morph, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.other.face_down_turn import can_turn_up_face_down_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.game_state import GameState
from engine.core.mana import ManaCost

_DISGUISE_COST_RE = re.compile(
    r'disguise\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)

DISGUISE_FACE_DOWN_MANA = 3


def has_disguise(card: CardInfo) -> bool:
    """Return True when the card has disguise."""
    oracle = card.oracle_text or ''
    return has_registered_keyword(oracle, 'Disguise') or bool(
        _DISGUISE_COST_RE.search(oracle)
    )


def disguise_turn_up_cost(card: CardInfo) -> ManaCost | None:
    """Parse the disguise cost to turn the card face up."""
    match = _DISGUISE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def disguise_turn_up_mana_needed(card: CardInfo) -> int:
    """Return generic mana to turn a disguised creature face up."""
    cost = disguise_turn_up_cost(card)
    if cost is None:
        return 0
    return cost.mana_value


def normalize_disguise_cast(card: CardInfo, cast_for_disguise: bool) -> bool:
    """Return whether this cast uses disguise (face-down 2/2)."""
    return cast_for_disguise and has_disguise(card) and card.is_creature


def disguise_face_down_mana_needed() -> tuple[int, int]:
    """Return mana and life to cast a creature face down with disguise."""
    return DISGUISE_FACE_DOWN_MANA, 0


def can_turn_up_disguise(
    perm: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when a face-down disguise creature may be turned face up."""
    return can_turn_up_face_down_keyword(
        perm, game, controller_idx, phase, has_disguise,
    )


def apply_turn_up_disguise(perm: Permanent) -> str | None:
    """Turn a disguise creature face up."""
    if not perm.face_down or perm.card_info is None:
        return None
    if not has_disguise(perm.card_info):
        return None
    perm.face_down = False
    return f"turned {perm.name} face up (disguise)"
