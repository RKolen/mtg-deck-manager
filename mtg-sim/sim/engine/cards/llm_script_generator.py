"""LLM fallback for generating card scripts when builtins and oracle infer fail."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable
from typing import Any

from deck_registry import CardInfo
from engine.cards.effect_serde import ALLOWED_EFFECT_TYPES, EffectDict, effects_from_json
from llm_client import generate_text, is_configured

logger = logging.getLogger(__name__)

GenerateFn = Callable[[str, float, int], str]

_EXAMPLE_BOLT = json.dumps([
    {'type': 'DealDamage', 'amount': 3, 'player_target': 'opponent'},
], indent=2)

_EXAMPLE_MODAL = json.dumps([
    {
        'type': 'Modal',
        'modes': [
            {'type': 'DestroyPermanent'},
            {'type': 'DealDamage', 'amount': 3, 'player_target': 'opponent'},
        ],
    },
], indent=2)


def llm_script_generation_enabled() -> bool:
    """Return True when LLM script seeding is opted in via environment."""
    return os.environ.get('LLM_SCRIPT_GENERATION', '').strip().lower() in (
        '1',
        'true',
        'yes',
    )


def build_card_script_prompt(card: CardInfo) -> str:
    """Build the structured-generation prompt for one card."""
    allowed = ', '.join(sorted(ALLOWED_EFFECT_TYPES))
    oracle = (card.oracle_text or '').strip()
    return (
        'You are generating a simplified MTG spell script as JSON for a rules engine.\n'
        'Return ONLY a JSON array of effect objects. No markdown outside the array.\n'
        f'Allowed effect types: {allowed}.\n'
        'Use multiple array entries for sequential effects (draw then discard).\n'
        'Use Modal with a modes array for "choose one" spells.\n'
        'Skip creature spells, lands, and effects you cannot model with allowed types.\n'
        'If the card cannot be modeled, return an empty JSON array: []\n\n'
        f'Example (Lightning Bolt):\n{_EXAMPLE_BOLT}\n\n'
        f'Example (choose one charm):\n{_EXAMPLE_MODAL}\n\n'
        f'Card name: {card.name}\n'
        f'Type line: {card.type_line}\n'
        f'Mana cost: {card.mana_cost}\n'
        f'Oracle text:\n{oracle}\n\n'
        'JSON array:'
    )


def _parse_llm_json_payload(text: str) -> list[Any] | None:
    """Extract a JSON effect array from raw LLM output."""
    stripped = text.strip()
    fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', stripped)
    if fence is not None:
        stripped = fence.group(1).strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        array_match = re.search(r'\[[\s\S]*\]', stripped)
        if array_match is None:
            return None
        try:
            data = json.loads(array_match.group(0))
        except json.JSONDecodeError:
            return None
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get('effects'), list):
        return data['effects']
    return None


def validate_effect_json_list(data: list[Any]) -> list[EffectDict] | None:
    """Validate LLM JSON against the effect serde schema."""
    if not data:
        return None
    try:
        effects_from_json(data)
    except (TypeError, ValueError, KeyError) as exc:
        logger.warning('LLM card script JSON failed validation: %s', exc)
        return None
    return data


def _llm_script_preconditions(card: CardInfo) -> str | None:
    """Return a skip reason when LLM script generation should not run."""
    if card.is_land or card.is_creature:
        return 'creature_or_land'
    if not (card.oracle_text or '').strip():
        return 'empty_oracle'
    if not llm_script_generation_enabled():
        return 'disabled'
    return None


def generate_card_script_json(
    card: CardInfo,
    *,
    generate_fn: GenerateFn | None = None,
) -> list[EffectDict] | None:
    """Ask the LLM for a card script JSON blob, or None when disabled or invalid."""
    if _llm_script_preconditions(card) is not None:
        return None

    runner = generate_fn
    if runner is None:
        if not is_configured():
            return None
        runner = generate_text

    raw = runner(build_card_script_prompt(card), 0.1, 768)
    if not raw:
        return None
    parsed = _parse_llm_json_payload(raw)
    if parsed is None:
        logger.warning('LLM card script for %r: could not parse JSON', card.name)
        return None
    validated = validate_effect_json_list(parsed)
    if validated is None:
        logger.warning('LLM card script for %r: validation failed', card.name)
        return None
    logger.info('LLM generated card script for %r (%d effect(s))', card.name, len(validated))
    return validated
