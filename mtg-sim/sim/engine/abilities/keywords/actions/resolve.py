"""Apply keyword actions from oracle text during spell and ability resolution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from engine.abilities.keywords.actions.counters import (
    bolster_amount,
    bolster_lowest_creature,
    counter_action_amount,
    has_bolster,
    has_counter_action,
    has_proliferate,
    has_support,
    proliferate,
    put_plus_counters,
    support_amount,
    support_creatures,
)
from engine.abilities.keywords.actions.detect import keyword_actions_in_oracle
from engine.abilities.keywords.actions.fight import fight_creatures, has_fight
from engine.abilities.keywords.actions.library import (
    discover_from_library,
    fateseal_cards,
    has_discover,
    has_fateseal,
    has_mill,
    has_scry,
    has_shuffle,
    has_surveil,
    mill_cards,
    mill_count,
    scry_cards,
    scry_count,
    shuffle_library,
    surveil_cards,
    surveil_count,
)
from engine.abilities.keywords.actions.tokens import (
    connive,
    create_creature_token_from_oracle,
    explore_creature,
    has_connive,
    has_create,
    has_explore,
    has_food,
    has_investigate,
    has_populate,
    has_treasure,
    food_token_blueprint,
    investigate,
    populate_token,
    treasure_token_blueprint,
    create_token_from_blueprint,
)
from engine.abilities.keywords.handlers import grant_regeneration_shield
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject, Permanent
from engine.core.zones import Zone, ZoneManager

if True:
    from engine.core.game_state import GameState

DrawFn = Callable[[int, int], list[CardObject]]


@dataclass
class ActionContext:
    """Inputs for resolving keyword actions on a spell or ability."""

    zones: ZoneManager
    game: GameState | None
    controller_idx: int
    oracle_text: str
    target_creature_uid: str | None = None
    second_creature_uid: str | None = None
    scry_bottom_indices: tuple[int, ...] = ()
    draw_fn: DrawFn | None = None
    skip_actions: frozenset[str] = field(default_factory=frozenset)


def _opponent_idx(controller_idx: int) -> int:
    return 1 - controller_idx


def _find_creature(zones: ZoneManager, uid: str | None) -> Permanent | None:
    if uid is None:
        return None
    try:
        return zones.find_permanent(int(uid))
    except ValueError:
        return None


def _apply_mill(ctx: ActionContext) -> str | None:
    if not has_mill(ctx.oracle_text):
        return None
    count = mill_count(ctx.oracle_text)
    if 'each player mills' in ctx.oracle_text.lower():
        parts = []
        for idx in (0, 1):
            milled = mill_cards(ctx.zones, idx, count)
            parts.append(f"P{idx + 1} milled {len(milled)}")
        return '; '.join(parts)
    if 'target player mills' in ctx.oracle_text.lower() or 'target opponent mills' in ctx.oracle_text.lower():
        victim = _opponent_idx(ctx.controller_idx)
        milled = mill_cards(ctx.zones, victim, count)
        return f"milled {len(milled)} (P{victim + 1})"
    milled = mill_cards(ctx.zones, ctx.controller_idx, count)
    return f"milled {len(milled)}"


def _apply_scry(ctx: ActionContext) -> str | None:
    if not has_scry(ctx.oracle_text):
        return None
    count = scry_count(ctx.oracle_text)
    bottomed = scry_cards(
        ctx.zones,
        ctx.controller_idx,
        count,
        ctx.scry_bottom_indices,
    )
    return f"scry {count} (put {bottomed} on bottom)"


def _apply_surveil(ctx: ActionContext) -> str | None:
    if not has_surveil(ctx.oracle_text):
        return None
    count = surveil_count(ctx.oracle_text)
    milled = surveil_cards(ctx.zones, ctx.controller_idx, count)
    return f"surveiled {milled} to graveyard"


def _apply_fateseal(ctx: ActionContext) -> str | None:
    if not has_fateseal(ctx.oracle_text):
        return None
    from engine.abilities.keywords.actions._parse import parse_amount_after_keyword
    count = parse_amount_after_keyword(ctx.oracle_text, 'fateseal')
    opponent = _opponent_idx(ctx.controller_idx)
    moved = fateseal_cards(ctx.zones, opponent, count)
    return f"fatesealed {moved} (P{opponent + 1})"


def _apply_fight(ctx: ActionContext) -> str | None:
    if not has_fight(ctx.oracle_text):
        return None
    fighter = _find_creature(ctx.zones, ctx.target_creature_uid)
    opponent = _find_creature(ctx.zones, ctx.second_creature_uid)
    if fighter is None or opponent is None:
        return "fight (need two creature targets)"
    dmg_a, dmg_b = fight_creatures(fighter, opponent)
    return f"{fighter.name} fought {opponent.name} ({dmg_a}/{dmg_b} damage)"


def _apply_proliferate(ctx: ActionContext) -> str | None:
    if not has_proliferate(ctx.oracle_text) or ctx.game is None:
        return None
    parts = proliferate(ctx.game)
    return 'proliferated' + (f" ({'; '.join(parts)})" if parts else '')


def _apply_bolster(ctx: ActionContext) -> str | None:
    if not has_bolster(ctx.oracle_text):
        return None
    amount = bolster_amount(ctx.oracle_text)
    name = bolster_lowest_creature(ctx.zones, ctx.controller_idx, amount)
    if name is None:
        return "bolster (no creatures)"
    return f"bolstered {name} (+{amount}/+{amount})"


def _apply_support(ctx: ActionContext) -> str | None:
    if not has_support(ctx.oracle_text):
        return None
    amount = support_amount(ctx.oracle_text)
    name = support_creatures(
        ctx.zones,
        ctx.controller_idx,
        amount,
        ctx.target_creature_uid,
    )
    if name is None:
        return "support (no target)"
    return f"supported {name} (+{amount}/+{amount})"


def _apply_counter_action(ctx: ActionContext) -> str | None:
    if not has_counter_action(ctx.oracle_text):
        return None
    amount = counter_action_amount(ctx.oracle_text)
    target = _find_creature(ctx.zones, ctx.target_creature_uid)
    if target is None:
        creatures = [
            p for p in ctx.zones.permanents_of(ctx.controller_idx)
            if 'Creature' in p.type_line
        ]
        target = creatures[-1] if creatures else None
    if target is None:
        return "counter (no target)"
    put_plus_counters(target, amount)
    return f"put {amount} +1/+1 counter(s) on {target.name}"


def _apply_connive(ctx: ActionContext) -> str | None:
    if not has_connive(ctx.oracle_text) or ctx.draw_fn is None:
        return None
    return connive(ctx.zones, ctx.controller_idx, ctx.oracle_text, ctx.draw_fn)


def _apply_explore(ctx: ActionContext) -> str | None:
    if not has_explore(ctx.oracle_text):
        return None
    target = _find_creature(ctx.zones, ctx.target_creature_uid)
    if target is None:
        creatures = [
            p for p in ctx.zones.permanents_of(ctx.controller_idx)
            if 'Creature' in p.type_line
        ]
        target = creatures[-1] if creatures else None
    if target is None:
        return "explore (no creature)"
    name = explore_creature(target)
    return f"{name} explored (+1/+1)"


def _apply_investigate(ctx: ActionContext) -> str | None:
    if not has_investigate(ctx.oracle_text):
        return None
    from engine.abilities.keywords.actions._parse import parse_amount_after_keyword
    times = parse_amount_after_keyword(ctx.oracle_text, 'investigate')
    names = investigate(ctx.zones, ctx.controller_idx, times)
    return f"investigated ({names})"


def _apply_create(ctx: ActionContext) -> str | None:
    if not has_create(ctx.oracle_text):
        return None
    name = create_creature_token_from_oracle(
        ctx.zones,
        ctx.controller_idx,
        ctx.oracle_text,
    )
    if name is None:
        return None
    return f"created {name}"


def _apply_populate(ctx: ActionContext) -> str | None:
    if not has_populate(ctx.oracle_text):
        return None
    name = populate_token(ctx.zones, ctx.controller_idx)
    if name is None:
        return "populate (no token to copy)"
    return f"populated {name}"


def _apply_treasure(ctx: ActionContext) -> str | None:
    if not has_treasure(ctx.oracle_text):
        return None
    from engine.abilities.keywords.actions._parse import parse_amount_after_keyword
    times = parse_amount_after_keyword(ctx.oracle_text, 'treasure')
    names = [
        create_token_from_blueprint(
            ctx.zones, ctx.controller_idx, treasure_token_blueprint(),
        )
        for _ in range(max(1, times))
    ]
    return f"treasure ({', '.join(names)})"


def _apply_food(ctx: ActionContext) -> str | None:
    if not has_food(ctx.oracle_text):
        return None
    from engine.abilities.keywords.actions._parse import parse_amount_after_keyword
    times = parse_amount_after_keyword(ctx.oracle_text, 'food')
    names = [
        create_token_from_blueprint(
            ctx.zones, ctx.controller_idx, food_token_blueprint(),
        )
        for _ in range(max(1, times))
    ]
    return f"food ({', '.join(names)})"


def _apply_shuffle(ctx: ActionContext) -> str | None:
    if not has_shuffle(ctx.oracle_text):
        return None
    if 'each player shuffles' in ctx.oracle_text.lower():
        shuffle_library(ctx.zones, 0)
        shuffle_library(ctx.zones, 1)
        return "each player shuffled"
    shuffle_library(ctx.zones, ctx.controller_idx)
    return "shuffled library"


def _apply_discover(ctx: ActionContext) -> str | None:
    if not has_discover(ctx.oracle_text):
        return None
    max_mv = 0
    match_text = ctx.oracle_text.lower()
    if 'discover' in match_text:
        from engine.abilities.keywords.actions._parse import parse_amount_after_keyword
        max_mv = parse_amount_after_keyword(ctx.oracle_text, 'discover')
    result = discover_from_library(ctx.zones, ctx.controller_idx, max_mv)
    if result.hit is None or result.hit.card_info is None:
        return f"discover {max_mv} (no hit, {result.bottom_count} to bottom)"
    ctx.zones.player_zones[ctx.controller_idx].hand.append(result.hit)
    return f"discovered {result.hit.card_info.name}"


def _apply_regenerate(ctx: ActionContext) -> str | None:
    if not has_registered_keyword(ctx.oracle_text, 'Regenerate'):
        return None
    target = _find_creature(ctx.zones, ctx.target_creature_uid)
    if target is None:
        return None
    grant_regeneration_shield(target)
    return f"{target.name} gains regeneration shield"


def _apply_destroy(ctx: ActionContext) -> str | None:
    if not has_registered_keyword(ctx.oracle_text, 'Destroy'):
        return None
    if 'destroy target' not in ctx.oracle_text.lower():
        return None
    target = _find_creature(ctx.zones, ctx.target_creature_uid)
    if target is None or ctx.game is None:
        return None
    ctx.zones.leave_battlefield(target, Zone.GRAVEYARD, 'destroy', ctx.game)
    return f"destroyed {target.name}"


def _apply_exile(ctx: ActionContext) -> str | None:
    if not has_registered_keyword(ctx.oracle_text, 'Exile'):
        return None
    if 'exile target' not in ctx.oracle_text.lower():
        return None
    target = _find_creature(ctx.zones, ctx.target_creature_uid)
    if target is None or not isinstance(target.source, CardObject):
        return None
    card = target.source
    ctx.zones.leave_battlefield(target, Zone.EXILE, 'exile', ctx.game)
    return f"exiled {target.name}"


_HANDLERS: dict[str, Callable[[ActionContext], str | None]] = {
    'Mill': _apply_mill,
    'Scry': _apply_scry,
    'Surveil': _apply_surveil,
    'Fateseal': _apply_fateseal,
    'Fight': _apply_fight,
    'Proliferate': _apply_proliferate,
    'Bolster': _apply_bolster,
    'Support': _apply_support,
    'Counter': _apply_counter_action,
    'Connive': _apply_connive,
    'Explore': _apply_explore,
    'Investigate': _apply_investigate,
    'Create': _apply_create,
    'Populate': _apply_populate,
    'Treasure': _apply_treasure,
    'Food': _apply_food,
    'Shuffle': _apply_shuffle,
    'Discover': _apply_discover,
    'Regenerate': _apply_regenerate,
    'Destroy': _apply_destroy,
    'Exile': _apply_exile,
}


def resolve_keyword_actions(ctx: ActionContext) -> list[str]:
    """Apply recognized keyword actions in oracle order; return log fragments."""
    parts: list[str] = []
    mill_applied = False
    for action_name in keyword_actions_in_oracle(ctx.oracle_text):
        if action_name in ctx.skip_actions:
            continue
        handler = _HANDLERS.get(action_name)
        if handler is None:
            continue
        detail = handler(ctx)
        if detail:
            parts.append(detail)
            if action_name == 'Mill':
                mill_applied = True
    # Mill often appears as "mills N" without the capitalized keyword token.
    if (
        has_mill(ctx.oracle_text)
        and not mill_applied
        and 'Mill' not in ctx.skip_actions
    ):
        detail = _apply_mill(ctx)
        if detail:
            parts.append(detail)
    return parts


def resolve_spell_keyword_actions(
    zones: ZoneManager,
    game: GameState | None,
    controller_idx: int,
    oracle_text: str,
    target_creature_uid: str | None,
    draw_fn: DrawFn | None,
    *,
    skip_actions: frozenset[str] = frozenset(),
    scry_bottom_indices: tuple[int, ...] = (),
    second_creature_uid: str | None = None,
) -> str:
    """Resolve keyword actions for a spell; return a combined detail string or empty."""
    ctx = ActionContext(
        zones=zones,
        game=game,
        controller_idx=controller_idx,
        oracle_text=oracle_text,
        target_creature_uid=target_creature_uid,
        second_creature_uid=second_creature_uid,
        scry_bottom_indices=scry_bottom_indices,
        draw_fn=draw_fn,
        skip_actions=skip_actions,
    )
    parts = resolve_keyword_actions(ctx)
    return '; '.join(parts)
