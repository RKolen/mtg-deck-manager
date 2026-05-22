"""Post-cast keyword modifiers (storm, cascade) to keep spell_stack.py small."""

from __future__ import annotations

from typing import Protocol

from engine.abilities.keywords.casting.cascade import (
    cascade_targets,
    has_cascade,
    make_cascade_spell,
    reveal_cascade_hit,
    return_cascade_bottom,
    spell_mana_value,
)
from engine.abilities.keywords.casting.storm import storm_copy_count, supports_storm_copies
from engine.core.game_object import CardObject, SpellOnStack, Target
from engine.core.game_state import GameState
from engine.game.helpers import SpellCastContext, require_card_info


class PostCastHost(Protocol):
    """Minimal surface for post-cast keyword hooks."""

    state: GameState


def apply_post_cast_modifiers(
    game: PostCastHost,
    player_idx: int,
    card: CardObject,
    targets: list[Target],
    context: SpellCastContext,
) -> list[str]:
    """Apply storm, cascade, and return log detail lines."""
    logs: list[str] = []
    card_info = require_card_info(card)
    copies = _push_storm_copies(game, player_idx, card, targets, context)
    if copies:
        logs.append(f"{card_info.name} + {copies} storm copy/copies")
    cascade_name = _push_cascade_cast(game, player_idx, card, targets)
    if cascade_name:
        logs.append(f"cascade cast {cascade_name}")
    return logs


def _push_storm_copies(
    game: PostCastHost,
    player_idx: int,
    card: CardObject,
    targets: list[Target],
    context: SpellCastContext,
) -> int:
    """Put storm copies on the stack above the spell that created them."""
    card_info = require_card_info(card)
    if not supports_storm_copies(card_info):
        return 0
    copies = storm_copy_count(game.state.players[player_idx].spells_cast_this_turn)
    for _ in range(copies):
        game.state.stack.push(SpellOnStack(
            controller_idx=player_idx,
            owner_idx=card.owner_idx,
            source=card,
            targets=list(targets),
            cast_via_flashback=context.cast_via_flashback,
            cast_via_escape=context.cast_via_escape,
            kicker_times=context.kicker_times,
            is_storm_copy=True,
        ))
    return copies


def _push_cascade_cast(
    game: PostCastHost,
    player_idx: int,
    cascade_source: CardObject,
    parent_targets: list[Target],
) -> str | None:
    """Exile for cascade and put a free spell on the stack if a hit is found."""
    source_info = require_card_info(cascade_source)
    if not has_cascade(source_info):
        return None
    library = game.state.zones.player_zones[player_idx].library
    reveal = reveal_cascade_hit(library, spell_mana_value(source_info))
    return_cascade_bottom(library, reveal.bottom_cards)
    if reveal.hit is None:
        return None
    hit_info = require_card_info(reveal.hit)
    hit_targets = cascade_targets(reveal.hit, parent_targets, player_idx)
    game.state.players[player_idx].spells_cast_this_turn += 1
    game.state.stack.push(make_cascade_spell(reveal.hit, player_idx, hit_targets))
    return hit_info.name
