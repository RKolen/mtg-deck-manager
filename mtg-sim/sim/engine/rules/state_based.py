"""
State-based actions (SBAs) for the MTG rules engine (CR 704).

SBAs are game rules checked automatically before any player receives
priority. They are applied simultaneously and then re-checked until no
new SBAs apply. No player choices are involved in SBA application except
for the legend rule and planeswalker uniqueness rule, where the controller
chooses which permanent to keep.

Phase A implements the full CR 704.5 list. More exotic SBAs (poison
counters, battle cards) are stubs that will be fleshed out in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.core.game_object import Permanent, TokenObject
from engine.core.game_state import GameState
from engine.core.zones import Zone


@dataclass
class SBAEvent:
    """Describes one state-based action that was applied."""

    rule: str
    description: str
    player_idx: int | None = None
    obj_id: int | None = None


def check_sbas(game: GameState) -> list[SBAEvent]:
    """Apply all CR 704 SBAs; repeat until none fire in one full pass.

    Returns the complete list of SBA events that fired, in order.
    Callers should check game.winner after this returns — player-loss SBAs
    set it directly.
    """
    all_events: list[SBAEvent] = []
    while True:
        batch = (
            _check_player_sbas(game)
            + _check_creature_sbas(game)
            + _check_planeswalker_sbas(game)
            + _check_legend_rule(game)
            + _check_attachment_sbas(game)
            + _check_token_sbas(game)
        )
        if not batch:
            break
        all_events.extend(batch)
    return all_events


# ---------------------------------------------------------------------------
# Per-category SBA checkers
# ---------------------------------------------------------------------------

def _check_player_sbas(game: GameState) -> list[SBAEvent]:
    """CR 704.5a life <= 0; CR 704.5c >= 10 poison."""
    events: list[SBAEvent] = []
    for idx, player in enumerate(game.players):
        if player.has_lost:
            continue
        if player.life <= 0:
            player.has_lost = True
            _set_winner(game, 1 - idx)
            events.append(SBAEvent(
                rule="704.5a",
                description=f"{player.name} has {player.life} life",
                player_idx=idx,
            ))
        elif player.poison >= 10:
            player.has_lost = True
            _set_winner(game, 1 - idx)
            events.append(SBAEvent(
                rule="704.5c",
                description=f"{player.name} has {player.poison} poison counters",
                player_idx=idx,
            ))
    return events


def _check_creature_sbas(game: GameState) -> list[SBAEvent]:
    """CR 704.5f toughness <= 0; CR 704.5g lethal damage."""
    events: list[SBAEvent] = []
    for perm in list(game.zones.battlefield):
        if not _is_creature(perm):
            continue
        toughness = _effective_toughness(perm)
        if toughness <= 0:
            game.zones.leave_battlefield(perm, Zone.GRAVEYARD, "sba")
            events.append(SBAEvent(
                rule="704.5f",
                description=f"{perm.name} has {toughness} toughness",
                obj_id=perm.obj_id,
            ))
        elif perm.damage_marked >= toughness and not _is_indestructible(perm):
            game.zones.leave_battlefield(perm, Zone.GRAVEYARD, "sba")
            events.append(SBAEvent(
                rule="704.5g",
                description=f"{perm.name} has {perm.damage_marked} damage (toughness {toughness})",
                obj_id=perm.obj_id,
            ))
    return events


def _check_planeswalker_sbas(game: GameState) -> list[SBAEvent]:
    """CR 704.5i planeswalker loyalty = 0."""
    events: list[SBAEvent] = []
    for perm in list(game.zones.battlefield):
        if not _is_planeswalker(perm):
            continue
        if perm.counters.get("loyalty", 1) <= 0:
            game.zones.leave_battlefield(perm, Zone.GRAVEYARD, "sba")
            events.append(SBAEvent(
                rule="704.5i",
                description=f"{perm.name} has 0 loyalty",
                obj_id=perm.obj_id,
            ))
    return events


def _check_legend_rule(game: GameState) -> list[SBAEvent]:
    """CR 704.5j two legendary permanents with the same name (same controller).

    The controller keeps the one with the lower timestamp (entered first);
    the newer one goes to graveyard. Phase B adds a player-choice prompt
    for the human player; Phase A auto-resolves to keep the older copy.
    """
    events: list[SBAEvent] = []
    for ctrl in (0, 1):
        seen: dict[str, Permanent] = {}
        for perm in list(game.zones.battlefield):
            if perm.controller_idx != ctrl or not _is_legendary(perm):
                continue
            name = perm.name
            if name in seen:
                older = seen[name] if seen[name].timestamp < perm.timestamp else perm
                newer = perm if older is seen[name] else seen[name]
                game.zones.leave_battlefield(newer, Zone.GRAVEYARD, "sba")
                events.append(SBAEvent(
                    rule="704.5j",
                    description=f"Legend rule: kept older {name}",
                    player_idx=ctrl,
                    obj_id=newer.obj_id,
                ))
                seen[name] = older
            else:
                seen[name] = perm
    return events


def _check_attachment_sbas(game: GameState) -> list[SBAEvent]:
    """CR 704.5m aura not attached to legal permanent; CR 704.5n equipment on non-creature."""
    events: list[SBAEvent] = []
    for perm in list(game.zones.battlefield):
        if perm.attached_to is None:
            continue
        host = game.zones.find_permanent(perm.attached_to)
        if _is_aura(perm):
            if host is None:
                game.zones.leave_battlefield(perm, Zone.GRAVEYARD, "sba")
                events.append(SBAEvent(
                    rule="704.5m",
                    description=f"Aura {perm.name} has no legal host",
                    obj_id=perm.obj_id,
                ))
        elif _is_equipment(perm):
            if host is not None and not _is_creature(host):
                perm.attached_to = None
                events.append(SBAEvent(
                    rule="704.5n",
                    description=f"Equipment {perm.name} fell off non-creature",
                    obj_id=perm.obj_id,
                ))
    return events


def _check_token_sbas(game: GameState) -> list[SBAEvent]:
    """CR 704.5d tokens in non-battlefield zones cease to exist.

    ZoneManager.leave_battlefield already handles token cessation, so this
    check covers tokens that somehow ended up in a player zone (e.g. via a
    replacement effect not yet implemented). It is defensive and should
    rarely fire after Phase B is complete.
    """
    events: list[SBAEvent] = []
    for player_zones in game.zones.player_zones:
        for zone_list in (
            player_zones.hand,
            player_zones.graveyard,
            player_zones.exile,
            player_zones.library,
        ):
            tokens = [c for c in zone_list if isinstance(c, TokenObject)]
            for token in tokens:
                zone_list.remove(token)
                events.append(SBAEvent(
                    rule="704.5d",
                    description=f"Token {token.name} ceased to exist outside battlefield",
                ))
    return events


# ---------------------------------------------------------------------------
# Permanent characteristic helpers (Phase A: card_info + counter deltas)
# Full layer-system computation replaces these in Phase F.
# ---------------------------------------------------------------------------

def _effective_toughness(perm: Permanent) -> int:
    """Toughness after +1/+1 and -1/-1 counters; minimum 0 for SBA check."""
    base = _base_toughness(perm)
    return base + perm.counters.get("+1/+1", 0) - perm.counters.get("-1/-1", 0)


def _base_toughness(perm: Permanent) -> int:
    """Printed toughness from the underlying card or token blueprint.

    CardInfo.numeric_toughness applies max(1, …) for combat safety, but SBAs
    must see the raw value so that a 0-toughness creature (e.g. after Humble)
    is correctly detected by CR 704.5f.
    """
    if perm.card_info is not None:
        try:
            raw = perm.card_info.pt.split("/", maxsplit=1)[1]
            return int(raw)
        except (ValueError, TypeError, IndexError):
            return 1
    if isinstance(perm.source, TokenObject):
        try:
            return int(perm.source.toughness)
        except (ValueError, TypeError):
            return 1
    return 1


def _is_creature(perm: Permanent) -> bool:
    return "Creature" in perm.type_line


def _is_legendary(perm: Permanent) -> bool:
    return "Legendary" in perm.type_line


def _is_planeswalker(perm: Permanent) -> bool:
    return "Planeswalker" in perm.type_line


def _is_aura(perm: Permanent) -> bool:
    return "Enchantment" in perm.type_line and "Aura" in perm.type_line


def _is_equipment(perm: Permanent) -> bool:
    return "Equipment" in perm.type_line


def _is_indestructible(perm: Permanent) -> bool:
    return "indestructible" in perm.oracle_text.lower()


def _set_winner(game: GameState, winner_idx: int) -> None:
    """Set game.winner if not already set."""
    if game.winner is None:
        game.winner = winner_idx
