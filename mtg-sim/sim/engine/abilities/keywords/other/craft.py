"""Craft: exile artifacts you control to transform this permanent."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.activated.core import activation_mana_value
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.game_state import GameState
from engine.core.zones import Zone

_CRAFT_ACTIVATION_RE = re.compile(
    r'(\{[^}]+\}(?:\{[^}]+\})*),\s*Exile.*?Craft',
    re.IGNORECASE | re.DOTALL,
)


def has_craft(perm: Permanent) -> bool:
    """Return True when the permanent has craft."""
    return has_keyword(perm, 'Craft')


def has_craft_card(card: CardInfo) -> bool:
    """Return True when the card has craft."""
    return has_registered_keyword(card.oracle_text, 'Craft')


def craft_mana_needed(perm: Permanent) -> int:
    """Return generic mana to activate craft (simplified)."""
    match = _CRAFT_ACTIVATION_RE.search(perm.oracle_text or '')
    if match is None:
        return 0
    return activation_mana_value(match.group(1))


def craft_artifact_error(
    game: GameState,
    perm: Permanent,
    player_idx: int,
    artifact_ids: list[int],
) -> str | None:
    """Return an error when craft artifact exiles are illegal."""
    message: str | None = None
    if not has_craft(perm):
        message = f"{perm.name} does not have craft"
    elif perm.controller_idx != player_idx:
        message = "You may only craft permanents you control"
    elif not artifact_ids:
        message = "Craft requires exiling at least one artifact you control"
    else:
        for artifact_id in artifact_ids:
            victim = game.zones.find_permanent(artifact_id)
            if victim is None:
                message = f"Craft artifact {artifact_id} not found"
                break
            if victim.controller_idx != player_idx:
                message = "Craft may only exile artifacts you control"
                break
            if 'Artifact' not in victim.type_line:
                message = f"{victim.name} is not an artifact"
                break
    return message


def apply_craft(
    game: GameState,
    perm: Permanent,
    artifact_ids: list[int],
) -> str | None:
    """Exile artifacts and mark the permanent crafted."""
    for artifact_id in artifact_ids:
        victim = game.zones.find_permanent(artifact_id)
        if victim is None:
            continue
        game.zones.leave_battlefield(victim, Zone.EXILE, 'craft', game)
    perm.counters['crafted'] = 1
    if re.search(r'\btransform\b', perm.oracle_text or '', re.IGNORECASE):
        perm.face_down = not perm.face_down
    return f"crafted {perm.name} (exiled {len(artifact_ids)} artifact(s))"
