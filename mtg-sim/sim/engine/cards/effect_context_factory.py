"""Build CardEffectContext without importing helpers from effects.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.cards.effects import CardEffectContext, _CardEffectTargets
from engine.game.helpers import creature_target_uids, target_player as target_player_from_targets

if TYPE_CHECKING:
    from engine.core.game_object import SpellOnStack
    from engine.core.game_state import GameState
    from engine.cards.effects import DrawFn


def card_effect_context_from_spell(
    game: GameState,
    spell: SpellOnStack,
    draw_fn: DrawFn | None = None,
) -> CardEffectContext:
    """Build context from a resolving spell on the stack."""
    card = spell.source
    if card is None:
        raise ValueError('spell has no source card')
    creature_uids = creature_target_uids(spell.targets)
    mode_idx = spell.modes[0] if spell.modes else None
    return CardEffectContext(
        game=game,
        controller_idx=spell.controller_idx,
        source=card,
        targets=_CardEffectTargets(
            player_idx=target_player_from_targets(spell.targets),
            creature_uid=creature_uids[0] if creature_uids else None,
            second_creature_uid=creature_uids[1] if len(creature_uids) > 1 else None,
        ),
        selected_mode=mode_idx,
        draw_fn=draw_fn,
    )
