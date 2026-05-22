"""Shared helpers for the interactive game package."""

from __future__ import annotations

from dataclasses import dataclass

from deck_registry import CardInfo
from engine.abilities.keywords import has_flash
from engine.cards.oracle_parse import TokenBlueprint, is_affordable, spell_category
from engine.core.game_object import (
    ActivatedAbilityOnStack,
    CardObject,
    Effect,
    GameObject,
    Permanent,
    TokenObject,
    TriggeredAbilityOnStack,
)
from engine.core.game_object import Target
from engine.core.game_state import GameState


@dataclass(frozen=True)
class SpellCastContext:
    """Options when placing a spell on the stack."""

    cast_via_flashback: bool = False
    from_graveyard: bool = False
    kicker_times: int = 0


def expand_deck(cards: list[CardInfo], player_idx: int) -> list[CardObject]:
    """Expand CardInfo quantities into CardObjects."""
    result: list[CardObject] = []
    for card in cards:
        if card.sideboard:
            continue
        for _ in range(card.quantity):
            result.append(CardObject(
                controller_idx=player_idx,
                owner_idx=player_idx,
                card_info=card,
            ))
    return result


def card_to_client(idx: int, card: CardInfo, available_mana: int) -> dict:
    """Serialise one hand card using the existing client shape."""
    return {
        "idx": idx,
        "name": card.name,
        "cmc": card.cmc,
        "type": card.short_type(),
        "power": card.numeric_power,
        "toughness": card.numeric_toughness,
        "oracle": card.oracle_text or "",
        "category": spell_category(card),
        "isLand": card.is_land,
        "isCreature": card.is_creature,
        "affordable": is_affordable(card, available_mana),
    }


def payment_requirements(card: CardInfo) -> tuple[int, int]:
    """Return mana and life needed for simplified payment."""
    phyrexian_pips = (card.mana_cost or "").upper().count("/P")
    total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
    return max(0, total_cmc - phyrexian_pips), phyrexian_pips * 2


def require_card_info(card: CardObject) -> CardInfo:
    """Return card_info for a real card object."""
    assert card.card_info is not None
    return card.card_info


def is_land(card: CardObject) -> bool:
    """Return True when the card object is a land."""
    return require_card_info(card).is_land


def can_cast_now(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return whether the player can cast a card in the current Phase B window."""
    if card.is_land:
        return False
    if has_instant_timing(card):
        return phase in ("main1", "main2", "attack", "declare_blockers")
    return phase in ("main1", "main2") and stack_is_empty


def has_instant_timing(card: CardInfo) -> bool:
    """Return whether a spell can be cast at instant speed."""
    return has_flash(card)


def targets_from_request(
    target_uid_str: str | None,
    target_player_idx: int | None,
) -> list[Target]:
    """Convert the legacy action payload target fields to stack targets."""
    targets: list[Target] = []
    if target_uid_str is not None:
        try:
            targets.append(Target(obj_id=int(target_uid_str)))
        except ValueError:
            return targets
    if target_player_idx is not None:
        targets.append(Target(player_idx=target_player_idx))
    return targets


def target_uid(targets: list[Target]) -> str | None:
    """Return the first permanent target as a legacy uid string."""
    target = next((t for t in targets if t.obj_id is not None), None)
    return str(target.obj_id) if target is not None else None


def target_player(targets: list[Target]) -> int | None:
    """Return the first player target index."""
    target = next((t for t in targets if t.player_idx is not None), None)
    return target.player_idx if target is not None else None


def resolve_ability_effect(
    obj: TriggeredAbilityOnStack | ActivatedAbilityOnStack,
    game: GameState,
) -> str:
    """Apply an ability effect if one is attached to the stack object."""
    if obj.effect is None:
        return "Resolved ability"
    detail = obj.effect.resolve(game, obj)
    return detail or "Resolved ability"


class CreateTokenEffect(Effect):
    """Effect that creates a token from a parsed token blueprint."""

    def __init__(self, blueprint: TokenBlueprint) -> None:
        self.blueprint = blueprint

    def resolve(self, game: GameState, source: GameObject) -> str:
        """Create the token controlled by the source permanent's controller."""
        if not isinstance(source, TriggeredAbilityOnStack):
            return ""
        source_permanent = game.zones.find_permanent(source.source_permanent_id)
        if source_permanent is None:
            return ""
        token = TokenObject(
            controller_idx=source_permanent.controller_idx,
            owner_idx=source_permanent.controller_idx,
            name=self.blueprint.name,
            type_line=self.blueprint.type_line,
            colors=self.blueprint.colors,
            power=self.blueprint.power,
            toughness=self.blueprint.toughness,
            oracle_text=self.blueprint.oracle_text,
        )
        game.zones.enter_battlefield(token, source_permanent.controller_idx, "heroic")
        return f"{source_permanent.name} created {self.blueprint.name}"

    def describe(self) -> str:
        """Return a short description for logs and debugging."""
        return f"Create {self.blueprint.name}"


def last_creature(permanents: list[Permanent]) -> Permanent | None:
    """Return the last creature on a list of permanents."""
    creatures = [p for p in permanents if "Creature" in p.type_line]
    return creatures[-1] if creatures else None


def card_names(cards: list[CardObject]) -> str:
    """Format card names for log messages."""
    return ", ".join(require_card_info(c).name for c in cards)


def perm_names(permanents: list[Permanent]) -> str:
    """Format permanent names for log messages."""
    return ", ".join(p.name for p in permanents)
