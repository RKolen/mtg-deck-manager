"""Ability words that appear on spells (Sweep, council votes, etc.)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.ability_words.clause import clause_after_ability_word
from engine.abilities.keywords.ability_words.detect import has_ability_word
from engine.cards.oracle_parse import parse_damage, parse_draw, parse_life_gain
from engine.core.game_state import GameState

_SPELL_HOSTED_WORDS: tuple[str, ...] = (
    'Sweep',
    'Secret council',
    'Will of the council',
    "Council's dilemma",
    'Will of the Planeswalkers',
)


def apply_spell_hosted_ability_words(
    game: GameState,
    card_info: CardInfo,
    controller_idx: int,
) -> list[str]:
    """Resolve on-cast clauses printed on the spell card itself."""
    oracle = card_info.oracle_text or ''
    details: list[str] = []
    for word in _SPELL_HOSTED_WORDS:
        if not has_ability_word(oracle, word):
            continue
        clause = clause_after_ability_word(oracle, word)
        if not clause:
            continue
        detail = _resolve_clause_for_controller(game, controller_idx, clause, word)
        if detail:
            details.append(detail)
    return details


def _resolve_clause_for_controller(
    game: GameState,
    controller_idx: int,
    clause: str,
    word: str,
) -> str:
    """Apply draw, damage, or life from a spell-hosted ability word clause."""
    parts: list[str] = []

    draw_count = parse_draw(clause)
    if draw_count > 0:
        drawn = 0
        for _ in range(draw_count):
            if game.zones.draw(controller_idx) is not None:
                drawn += 1
        parts.append(f"drew {drawn} card(s)")

    damage = parse_damage(clause)
    if damage > 0:
        opponent = 1 - controller_idx
        game.players[opponent].life -= damage
        game.mark_player_was_dealt_damage(opponent)
        parts.append(f"dealt {damage} damage")

    life = parse_life_gain(clause)
    if life > 0:
        game.gain_life(controller_idx, life)
        parts.append(f"gained {life} life")

    if parts:
        return f"{word}: {', '.join(parts)}"
    return f"{word}: cast"
