"""
AI casting and board-evaluation heuristics.

Ported from game_engine._opp_play_card and extended with typed interfaces
for the new engine. These are temporary heuristics used until Phase I
implements the full priority-aware agent (engine/ai/agent.py).

The functions here are pure: they read game state but do not mutate it.
Mutation is the caller's responsibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.cards.oracle_parse import spell_category, parse_damage, parse_pump
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from deck_registry import CardInfo


def choose_castable(
    hand: list[CardInfo],
    available_mana: int,
) -> list[tuple[int, CardInfo]]:
    """Return (hand_idx, card) pairs that are affordable, cheapest first.

    Creatures are prioritised over non-creatures at equal cost, matching
    the old engine's casting heuristic.
    """
    affordable = [
        (i, c) for i, c in enumerate(hand)
        if not c.is_land and int(c.cmc) <= available_mana
    ]
    return sorted(affordable, key=lambda t: (not t[1].is_creature, t[1].cmc))


def score_board(permanents: list[Permanent]) -> int:
    """Heuristic board score: sum of (power * toughness) for all creatures.

    A higher score means more threatening board presence.
    """
    total = 0
    for perm in permanents:
        if perm.card_info and perm.card_info.is_creature:
            total += perm.card_info.numeric_power * perm.card_info.numeric_toughness
    return total


def ai_burn_target(opponent_life: int, opponent_creatures: list[Permanent]) -> str:
    """Decide whether the AI should burn the player or a creature.

    Returns 'player' to target the player, or the uid of the biggest threat.
    Phase A heuristic: finish off the player if they are at low life;
    otherwise remove the most dangerous creature on the board.
    """
    if opponent_life <= 3:
        return "player"
    big_threats = [
        p for p in opponent_creatures
        if p.card_info and p.card_info.numeric_power >= 3
    ]
    if big_threats:
        return str(big_threats[0].obj_id)
    return "player"


def ai_removal_target(opponent_creatures: list[Permanent]) -> Permanent | None:
    """Return the highest-power creature for the AI to remove, or None."""
    creatures = [p for p in opponent_creatures if p.card_info and p.card_info.is_creature]
    if not creatures:
        return None
    return max(creatures, key=lambda p: p.card_info.numeric_power if p.card_info else 0)


def ai_pump_target(own_creatures: list[Permanent]) -> Permanent | None:
    """Return the highest-power friendly creature to pump, or None."""
    creatures = [p for p in own_creatures if p.card_info and p.card_info.is_creature]
    if not creatures:
        return None
    return max(creatures, key=lambda p: p.card_info.numeric_power if p.card_info else 0)


def ai_resolve_card(
    card: CardInfo,
    own_creatures: list[Permanent],
    opp_creatures: list[Permanent],
    opp_life: int,
) -> dict:
    """Return a simplified resolution plan for one AI-cast card.

    The returned dict describes what effect to apply; the game loop
    (Phase B) reads it and mutates the game state. Keys vary by category.
    """
    category = spell_category(card)
    if category == "creature":
        return {"type": "creature"}
    if category == "burn":
        dmg = parse_damage(card.oracle_text or "") or max(1, int(card.cmc))
        target = ai_burn_target(opp_life, opp_creatures)
        return {"type": "burn", "damage": dmg, "target": target}
    if category == "removal":
        victim = ai_removal_target(opp_creatures)
        return {"type": "removal", "target_uid": str(victim.obj_id) if victim else None}
    if category == "pump":
        pp, pt = parse_pump(card.oracle_text or "")
        target = ai_pump_target(own_creatures)
        return {"type": "pump", "pp": pp, "pt": pt,
                "target_uid": str(target.obj_id) if target else None}
    return {"type": "spell"}
