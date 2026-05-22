"""Shared test fixtures for the MTG engine test suite.

All fixtures are plain functions so they can be called with arbitrary
parameters inside test functions. Import directly from this module.
"""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords import enters_ready
from engine.core.game_object import CardObject, Permanent
from engine.core.game_state import GameState, PlayerInfo
from engine.core.turn_structure import TurnRunner
from engine.core.zones import ZoneManager
from engine.rules.stack import Stack


# ---------------------------------------------------------------------------
# CardInfo builders
# ---------------------------------------------------------------------------

def make_card(
    name: str = "Test Card",
    type_line: str = "Creature — Human",
    cmc: float = 2.0,
    pt: str = "2/2",
    oracle: str = "",
    mana_cost: str = "",
) -> CardInfo:
    """Create a CardInfo with sensible defaults for testing."""
    return CardInfo(
        name=name,
        quantity=1,
        sideboard=False,
        cmc=cmc,
        type_line=type_line,
        pt=pt,
        oracle_text=oracle,
        mana_cost=mana_cost,
    )


def make_land(name: str = "Plains", color: str = "W") -> CardInfo:
    """Create a basic land CardInfo that produces the given color."""
    return CardInfo(
        name=name,
        quantity=1,
        sideboard=False,
        cmc=0.0,
        type_line="Basic Land — Plains",
        pt="0/0",
        oracle_text="",
        mana_cost="",
        produced_mana=[color],
    )


def make_deck(*cards: CardInfo, lands: int = 20) -> list[CardInfo]:
    """Create a deterministic test deck from explicit cards plus basic lands."""
    return list(cards) + [make_land() for _ in range(lands)]


def make_creature(
    name: str = "Grizzly Bears",
    power: int = 2,
    toughness: int = 2,
    cmc: float = 2.0,
    oracle: str = "",
    mana_cost: str = "{1}{G}",
) -> CardInfo:
    """Create a creature CardInfo."""
    return make_card(
        name=name,
        type_line="Creature — Bear",
        cmc=cmc,
        pt=f"{power}/{toughness}",
        oracle=oracle,
        mana_cost=mana_cost,
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
        cmc=cmc,
        oracle=oracle,
        mana_cost=mana_cost,
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
        PlayerInfo(name=player_name, life=player_life),
        PlayerInfo(name=opponent_name, life=opponent_life),
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
