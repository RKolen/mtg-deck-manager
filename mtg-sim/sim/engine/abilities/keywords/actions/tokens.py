"""Token and emblem-style keyword actions: Create, Investigate, Explore, Connive, Populate."""

from __future__ import annotations

import re

from engine.abilities.keywords.actions._parse import word_to_int
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.abilities.keywords.actions.detect import has_keyword_action
from engine.abilities.keywords.actions.library import mill_cards
from engine.abilities.keywords._token_factory import enter_token_from_blueprint
from engine.cards.oracle_parse import TokenBlueprint, parse_token_blueprint
from engine.core.game_object import Permanent, TokenObject
from engine.core.zones import ZoneManager

_CONNIVE_MILL_RE = re.compile(
    r'connive (\w+|\d+)',
    re.IGNORECASE,
)


def has_create(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Create action."""
    return has_keyword_action(oracle_text, 'Create')


def has_investigate(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Investigate action."""
    return has_keyword_action(oracle_text, 'Investigate')


def has_explore(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Explore action."""
    return has_keyword_action(oracle_text, 'Explore')


def has_connive(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Connive action."""
    return has_keyword_action(oracle_text, 'Connive')


def has_populate(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Populate action."""
    return has_keyword_action(oracle_text, 'Populate')


def has_treasure(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Treasure action."""
    return has_keyword_action(oracle_text, 'Treasure')


def has_food(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Food action."""
    return has_keyword_action(oracle_text, 'Food')


def connive_mill_count(oracle_text: str) -> int:
    """Parse mill amount from 'Connive N' (default 2)."""
    match = _CONNIVE_MILL_RE.search(oracle_text)
    if match is None:
        return 2
    return word_to_int(match.group(1))


def clue_token_blueprint() -> TokenBlueprint:
    """Standard Clue token for Investigate."""
    return TokenBlueprint(
        name='Clue Token',
        type_line='Artifact — Clue',
        power='0',
        toughness='0',
        oracle_text='{2}, Sacrifice this artifact: Draw a card.',
    )


def treasure_token_blueprint() -> TokenBlueprint:
    """Standard Treasure token."""
    return TokenBlueprint(
        name='Treasure Token',
        type_line='Artifact — Treasure',
        power='0',
        toughness='0',
        oracle_text='{T}, Sacrifice this artifact: Add one mana of any color.',
    )


def food_token_blueprint() -> TokenBlueprint:
    """Standard Food token."""
    return TokenBlueprint(
        name='Food Token',
        type_line='Artifact — Food',
        power='0',
        toughness='0',
        oracle_text='{2}, {T}, Sacrifice this artifact: You gain 3 life.',
    )


def create_token_from_blueprint(
    zones: ZoneManager,
    controller_idx: int,
    blueprint: TokenBlueprint,
) -> str:
    """Create a token permanent and return its display name."""
    return enter_token_from_blueprint(zones, controller_idx, blueprint, cause='token')


def create_creature_token_from_oracle(
    zones: ZoneManager,
    controller_idx: int,
    oracle_text: str,
) -> str | None:
    """Create a creature token when oracle contains a parseable create clause."""
    blueprint = parse_token_blueprint(oracle_text)
    if blueprint is None:
        return None
    return create_token_from_blueprint(zones, controller_idx, blueprint)


def investigate(zones: ZoneManager, controller_idx: int, times: int = 1) -> str:
    """Create Clue tokens for Investigate."""
    names: list[str] = []
    for _ in range(max(1, times)):
        names.append(create_token_from_blueprint(
            zones, controller_idx, clue_token_blueprint(),
        ))
    return ', '.join(names)


def explore_creature(perm: Permanent) -> str:
    """Explore (MVP): put a +1/+1 counter on the exploring creature."""
    put_plus_counters(perm, 1)
    return perm.name


def connive(
    zones: ZoneManager,
    controller_idx: int,
    oracle_text: str,
    draw_fn,
) -> str:
    """Connive: draw a card, then mill N."""
    drawn = draw_fn(controller_idx, 1)
    mill_n = connive_mill_count(oracle_text)
    milled = mill_cards(zones, controller_idx, mill_n)
    draw_label = drawn[0].card_info.name if drawn and drawn[0].card_info else 'a card'
    return f"connived (drew {draw_label}, milled {len(milled)})"


def populate_token(
    zones: ZoneManager,
    controller_idx: int,
) -> str | None:
    """Populate (MVP): copy the largest token you control."""
    tokens = [
        p for p in zones.permanents_of(controller_idx)
        if p.is_token and isinstance(p.source, TokenObject)
    ]
    if not tokens:
        return None
    source_token = max(
        tokens,
        key=lambda p: (
            int(p.source.power) if isinstance(p.source, TokenObject) else 0,
            int(p.source.toughness) if isinstance(p.source, TokenObject) else 0,
        ),
    )
    if not isinstance(source_token.source, TokenObject):
        return None
    src = source_token.source
    blueprint = TokenBlueprint(
        name=src.name,
        type_line=src.type_line,
        power=src.power,
        toughness=src.toughness,
        colors=list(src.colors),
        oracle_text=src.oracle_text,
    )
    return create_token_from_blueprint(zones, controller_idx, blueprint)
