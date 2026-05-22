"""Cascade: on cast, exile until a lower-mana nonland; may cast it free (CR 702.41)."""

from __future__ import annotations

from dataclasses import dataclass

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.cards.oracle_parse import spell_category
from engine.core.game_object import CardObject, SpellOnStack, Target, ZoneCard


@dataclass(frozen=True)
class CascadeReveal:
    """Result of exiling for cascade."""

    hit: CardObject | None
    bottom_cards: list[CardObject]


def has_cascade(card: CardInfo) -> bool:
    """Return True when the card has cascade."""
    return has_registered_keyword(card.oracle_text, 'Cascade')


def spell_mana_value(card: CardInfo) -> int:
    """Return mana value used for cascade comparison."""
    return int(card.cmc) if card.cmc == int(card.cmc) else int(card.cmc)


def reveal_cascade_hit(
    library: list[ZoneCard],
    max_mana_value: int,
) -> CascadeReveal:
    """Exile from the top of the library until a qualifying card is found."""
    exiled: list[CardObject] = []
    hit: CardObject | None = None
    while library:
        top = library.pop(0)
        if not isinstance(top, CardObject):
            continue
        card = top
        exiled.append(card)
        info = card.card_info
        if (
            hit is None
            and info is not None
            and not info.is_land
            and spell_mana_value(info) < max_mana_value
        ):
            hit = card
            break
    bottom = [card for card in exiled if card is not hit]
    return CascadeReveal(hit=hit, bottom_cards=bottom)


def return_cascade_bottom(library: list[ZoneCard], bottom: list[CardObject]) -> None:
    """Put exiled non-hit cards on the bottom of the library in order."""
    library.extend(bottom)


def cascade_targets(
    card: CardObject,
    parent_targets: list[Target],
    controller_idx: int,
) -> list[Target]:
    """Choose default targets for a cascade cast (MVP: inherit burn target)."""
    info = card.card_info
    if info is None:
        return []
    if spell_category(info) == 'burn':
        player_target = next((t for t in parent_targets if t.player_idx is not None), None)
        if player_target is not None:
            return [Target(player_idx=player_target.player_idx)]
        return [Target(player_idx=1 - controller_idx)]
    if parent_targets and parent_targets[0].obj_id is not None:
        return [Target(obj_id=parent_targets[0].obj_id)]
    return []


def make_cascade_spell(
    card: CardObject,
    controller_idx: int,
    targets: list[Target],
) -> SpellOnStack:
    """Build a free cascade spell on the stack."""
    return SpellOnStack(
        controller_idx=controller_idx,
        owner_idx=card.owner_idx,
        source=card,
        targets=targets,
        cast_via_cascade=True,
    )
