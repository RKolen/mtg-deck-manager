"""Shared test fixtures for the MTG engine test suite.

All fixtures are plain functions so they can be called with arbitrary
parameters inside test functions. Import directly from this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deck_registry import CardInfo, ManaProfile
from engine.abilities.keywords import enters_ready
from engine.core.game_object import CardObject, Permanent
from engine.core.game_state import GameState, PlayerInfo, _PlayerVitals
from engine.core.turn_structure import TurnRunner
from engine.core.zones import Zone, ZoneManager
from engine.game.cast_context import (
    CastAnnounceOptions,
    CastManaReductionIds,
    CastModifierIds,
    CastTargetingIds,
    _SacrificeTargetIds,
    HandAlternateCastChoices,
    HandCastCostChoices,
    _CostConditionAlts,
    _PaidSacrificeCosts,
    _RepeatCostChoices,
)
from engine.game.face_alternate_cast import FaceAlternateCastFlags
from engine.rules.combat import resolve_combat_damage
from engine.rules.stack import Stack


# ---------------------------------------------------------------------------
# Cast / combat helpers
# ---------------------------------------------------------------------------

_MODIFIER_KW_KEYS = frozenset({
    "bestow_target_uid",
    "mutate_target_uid",
    "emerge_sacrifice_ids",
    "casualty_sacrifice_ids",
    "spree_mode_indices",
    "convoke_creature_ids",
    "delve_graveyard_indices",
    "improvise_artifact_ids",
    "sneak_land_hand_indices",
    "assist_mana",
    "bargain_sacrifice_ids",
    "escalate_extra_targets",
})


def _as_tuple(values: tuple[int, ...] | list[int]) -> tuple[int, ...]:
    return tuple(values)


def _modifier_ids_from_kw(modifier_kw: dict[str, Any]) -> CastModifierIds:
    return CastModifierIds(
        targeting=CastTargetingIds(
            bestow_target_uid=modifier_kw.get("bestow_target_uid"),
            mutate_target_uid=modifier_kw.get("mutate_target_uid"),
            escalate_extra_targets=int(modifier_kw.get("escalate_extra_targets", 0)),
            spree_mode_indices=_as_tuple(modifier_kw.get("spree_mode_indices", ())),
            sacrifices=_SacrificeTargetIds(
                emerge_sacrifice_ids=_as_tuple(modifier_kw.get("emerge_sacrifice_ids", ())),
                casualty_sacrifice_ids=_as_tuple(modifier_kw.get("casualty_sacrifice_ids", ())),
                bargain_sacrifice_ids=_as_tuple(modifier_kw.get("bargain_sacrifice_ids", ())),
            ),
        ),
        reductions=CastManaReductionIds(
            convoke_creature_ids=_as_tuple(modifier_kw.get("convoke_creature_ids", ())),
            delve_graveyard_indices=_as_tuple(modifier_kw.get("delve_graveyard_indices", ())),
            improvise_artifact_ids=_as_tuple(modifier_kw.get("improvise_artifact_ids", ())),
            sneak_land_hand_indices=_as_tuple(modifier_kw.get("sneak_land_hand_indices", ())),
            assist_mana=int(modifier_kw.get("assist_mana", 0)),
        ),
    )


def cast_announce_options(**kwargs: Any) -> CastAnnounceOptions:
    """Build CastAnnounceOptions for integration tests."""
    flat = dict(kwargs)
    modifier_kw = {key: flat.pop(key) for key in list(flat) if key in _MODIFIER_KW_KEYS}
    return CastAnnounceOptions(
        costs=HandCastCostChoices(
            entwined=bool(flat.get("entwined", False)),
            overloaded=bool(flat.get("overloaded", False)),
            paid_buyback=bool(flat.get("paid_buyback", False)),
            paid=_PaidSacrificeCosts(
                paid_casualty=bool(flat.get("paid_casualty", False)),
                paid_conspire=bool(flat.get("paid_conspire", False)),
                paid_bargain=bool(flat.get("paid_bargain", False)),
                paid_demonstrate=bool(flat.get("paid_demonstrate", False)),
            ),
            repeat=_RepeatCostChoices(
                kicker_times=int(flat.get("kicker_times", 0)),
                replicate_times=int(flat.get("replicate_times", 0)),
            ),
        ),
        alternate=HandAlternateCastChoices(
            cast_for_emerge=bool(flat.get("cast_for_emerge", False)),
            cast_for_evoke=bool(flat.get("cast_for_evoke", False)),
            cast_for_mutate=bool(flat.get("cast_for_mutate", False)),
            cast_for_cleave=bool(flat.get("cast_for_cleave", False)),
            conditions=_CostConditionAlts(
                cast_for_miracle=bool(flat.get("cast_for_miracle", False)),
                cast_for_freerunning=bool(flat.get("cast_for_freerunning", False)),
                cast_for_spectacle=bool(flat.get("cast_for_spectacle", False)),
            ),
            face=FaceAlternateCastFlags(
                cast_for_morph=bool(flat.get("cast_for_morph", False)),
                cast_for_disguise=bool(flat.get("cast_for_disguise", False)),
                cast_for_dash=bool(flat.get("cast_for_dash", False)),
                cast_for_blitz=bool(flat.get("cast_for_blitz", False)),
            ),
        ),
        modifiers=_modifier_ids_from_kw(modifier_kw),
    )


def resolve_single_attacker(
    game: GameState,
    attacker: Permanent,
    *,
    attacking_player_idx: int = 1,
    defending_player_idx: int = 0,
    blocker_assignments: dict[str, str] | None = None,
):
    """Resolve combat damage for one attacker (shared by keyword/combat tests)."""
    return resolve_combat_damage(
        game,
        attacking_player_idx=attacking_player_idx,
        defending_player_idx=defending_player_idx,
        attacker_ids=[str(attacker.obj_id)],
        blocker_assignments=blocker_assignments or {},
    )


def resolve_player_attacks(
    game: GameState,
    attacker: Permanent,
    *,
    blocker_assignments: dict[str, str] | None = None,
):
    """Player 0 attacks player 1 with a single attacker."""
    return resolve_single_attacker(
        game,
        attacker,
        attacking_player_idx=0,
        defending_player_idx=1,
        blocker_assignments=blocker_assignments,
    )


def put_lands_on_battlefield(game: Any, count: int, player_idx: int = 0) -> None:
    """Put untapped lands onto the battlefield for integration-style tests."""
    zones = game.state.zones if hasattr(game, 'state') else game.zones
    for _ in range(count):
        land = CardObject(
            controller_idx=player_idx,
            owner_idx=player_idx,
            card_info=make_land(),
        )
        zones.enter_battlefield(land, player_idx, 'test_setup', Zone.HAND)


# ---------------------------------------------------------------------------
# CardInfo builders
# ---------------------------------------------------------------------------

@dataclass
class _CardStats:
    """Optional CMC and PT override for make_card."""

    cmc: float = 2.0
    pt: str = "2/2"


def make_card(
    name: str = "Test Card",
    type_line: str = "Creature — Human",
    oracle: str = "",
    mana_cost: str = "",
    stats: _CardStats | None = None,
) -> CardInfo:
    """Create a CardInfo with sensible defaults for testing."""
    st = stats or _CardStats()
    return CardInfo(
        name=name,
        quantity=1,
        sideboard=False,
        mana=ManaProfile(cmc=st.cmc, cost=mana_cost),
        type_line=type_line,
        pt=st.pt,
        oracle_text=oracle,
    )


def make_land(name: str = "Plains", color: str = "W") -> CardInfo:
    """Create a basic land CardInfo that produces the given color."""
    return CardInfo(
        name=name,
        quantity=1,
        sideboard=False,
        mana=ManaProfile(cmc=0.0, cost="", produced=[color]),
        type_line="Basic Land — Plains",
        pt="0/0",
        oracle_text="",
    )


def make_deck(*cards: CardInfo, lands: int = 20) -> list[CardInfo]:
    """Create a deterministic test deck from explicit cards plus basic lands."""
    return list(cards) + [make_land() for _ in range(lands)]


def make_creature(
    name: str = "Grizzly Bears",
    power: int = 2,
    toughness: int = 2,
    oracle: str = "",
    mana_cost: str = "{1}{G}",
) -> CardInfo:
    """Create a creature CardInfo."""
    return make_card(
        name=name,
        type_line="Creature — Bear",
        oracle=oracle,
        mana_cost=mana_cost,
        stats=_CardStats(cmc=2.0, pt=f"{power}/{toughness}"),
    )


def make_instant(
    name: str = "Test Instant",
    cmc: float = 1.0,
    oracle: str = "",
    mana_cost: str = "{R}",
) -> CardInfo:
    """Create a non-creature instant CardInfo."""
    return make_card(
        name=name,
        type_line="Instant",
        oracle=oracle,
        mana_cost=mana_cost,
        stats=_CardStats(cmc=cmc, pt="0/0"),
    )


def make_artifact(
    name: str = "Test Artifact",
    cmc: float = 2.0,
    oracle: str = "",
    mana_cost: str = "{2}",
) -> CardInfo:
    """Create an artifact CardInfo."""
    return make_card(
        name=name,
        type_line="Artifact",
        oracle=oracle,
        mana_cost=mana_cost,
        stats=_CardStats(cmc=cmc, pt="0/0"),
    )


# ---------------------------------------------------------------------------
# Zone helpers
# ---------------------------------------------------------------------------

def place_on_battlefield(
    card_info: CardInfo,
    player_idx: int,
    zones: ZoneManager,
    sick: bool = True,
) -> Permanent:
    """Create a CardObject and enter it onto the battlefield as a Permanent."""
    card_obj = CardObject(
        controller_idx=player_idx,
        owner_idx=player_idx,
        card_info=card_info,
    )
    perm = zones.enter_battlefield(card_obj, player_idx, "test_setup")
    if not enters_ready(perm):
        perm.sick = sick
    return perm


def add_to_hand(
    card_info: CardInfo,
    player_idx: int,
    zones: ZoneManager,
) -> CardObject:
    """Create a CardObject and place it in the player's hand."""
    card_obj = CardObject(
        controller_idx=player_idx,
        owner_idx=player_idx,
        card_info=card_info,
    )
    zones.player_zones[player_idx].hand.append(card_obj)
    return card_obj


def add_to_library(
    card_info: CardInfo,
    player_idx: int,
    zones: ZoneManager,
) -> CardObject:
    """Create a CardObject and place it on top of the player's library."""
    card_obj = CardObject(
        controller_idx=player_idx,
        owner_idx=player_idx,
        card_info=card_info,
    )
    zones.player_zones[player_idx].library.insert(0, card_obj)
    return card_obj


def fresh_zones(
    player_cards: list[CardInfo] | None = None,
    opponent_cards: list[CardInfo] | None = None,
) -> ZoneManager:
    """Return zones with the provided cards loaded into each player's library."""
    zones = ZoneManager()
    for card_info in player_cards or []:
        add_to_library(card_info, 0, zones)
    for card_info in opponent_cards or []:
        add_to_library(card_info, 1, zones)
    return zones


# ---------------------------------------------------------------------------
# GameState builder
# ---------------------------------------------------------------------------

def fresh_game(
    player_name: str = "Player",
    opponent_name: str = "Opponent",
    player_life: int = 20,
    opponent_life: int = 20,
) -> GameState:
    """Return a minimal GameState for testing with empty zones."""
    zones = ZoneManager()
    players = [
        PlayerInfo(name=player_name, vitals=_PlayerVitals(life=player_life)),
        PlayerInfo(name=opponent_name, vitals=_PlayerVitals(life=opponent_life)),
    ]
    runner = TurnRunner()
    runner.begin_turn(active_player_idx=0)
    runner.auto_advance_untap()
    stack = Stack()
    return GameState(
        game_id="test",
        zones=zones,
        players=players,
        turn=runner,
        stack=stack,
    )


# ---------------------------------------------------------------------------
# Shared card/game setup helpers (used across multiple test modules)
# ---------------------------------------------------------------------------

def make_entwine_charm(entwine_cost_str: str) -> CardInfo:
    """Return a modal instant with entwine using the given cost string."""
    return make_instant(
        'Charm',
        cmc=0,
        oracle=(
            'Choose one —\n'
            '• Charm deals 2 damage to any target.\n'
            '• Target player draws a card.\n'
            f'Entwine {entwine_cost_str}'
        ),
    )


def hexproof_game_setup() -> tuple[GameState, Permanent]:
    """Return a game and a hexproof creature controlled by player 0."""
    game = fresh_game()
    protected = place_on_battlefield(
        make_creature('Slippery', oracle='Hexproof'),
        0,
        game.zones,
    )
    return game, protected
