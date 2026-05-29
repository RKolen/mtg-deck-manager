"""Shared top-of-library reveal scoring for clash/parley-style effects."""

from __future__ import annotations

from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager


def library_top_mana_scores(
    zones: ZoneManager,
) -> list[tuple[int, int, str]]:
    """Return (player_idx, mana_value, card_name) for each player's top library card."""
    scores: list[tuple[int, int, str]] = []
    for pidx in (0, 1):
        library = zones.player_zones[pidx].library
        if not library:
            scores.append((pidx, -1, ''))
            continue
        top = library[-1]
        if isinstance(top, CardObject) and top.card_info is not None:
            mv = int(top.card_info.cmc)
            name = top.card_info.name
        else:
            mv = 0
            name = 'card'
        scores.append((pidx, mv, name))
    return scores


def resolve_top_card_contest(
    zones: ZoneManager,
    *,
    prefix: str,
) -> str:
    """Reveal tops, draw for the highest mana value, and return a log line."""
    scores = library_top_mana_scores(zones)
    winner_idx, best_mv, winner_card = max(scores, key=lambda item: item[1])
    if best_mv < 0:
        return f'{prefix} (no libraries)'
    drawn = zones.draw(winner_idx)
    draw_name = (
        drawn.card_info.name
        if drawn is not None and isinstance(drawn, CardObject) and drawn.card_info
        else 'nothing'
    )
    return f"{prefix}: P{winner_idx + 1} won with {winner_card} (MV {best_mv}), drew {draw_name}"
