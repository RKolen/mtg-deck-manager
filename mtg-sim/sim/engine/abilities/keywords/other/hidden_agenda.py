"""Hidden agenda and double agenda: secretly name cards (CR 702.106, simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_hidden_agenda(card: CardInfo) -> bool:
    """Return True when the card has hidden agenda."""
    return has_registered_keyword(card.oracle_text, 'Hidden agenda')


def has_double_agenda(card: CardInfo) -> bool:
    """Return True when the card has double agenda."""
    return has_registered_keyword(card.oracle_text, 'Double agenda')


def register_hidden_agenda(game: GameState, player_idx: int, card_name: str) -> None:
    """Secretly choose a card name for hidden agenda."""
    game.players[player_idx].hidden_agenda_name = card_name


def register_double_agenda(
    game: GameState,
    player_idx: int,
    first_name: str,
    second_name: str,
) -> None:
    """Secretly choose two card names for double agenda."""
    game.players[player_idx].double_agenda_names = (first_name, second_name)


def reveal_hidden_agenda(game: GameState, player_idx: int) -> str | None:
    """Reveal a hidden agenda name."""
    player = game.players[player_idx]
    if player.hidden_agenda_revealed or not player.hidden_agenda_name:
        return None
    player.hidden_agenda_revealed = True
    return f"hidden agenda revealed {player.hidden_agenda_name}"


def apply_hidden_agenda_on_spell_cast(
    game: GameState,
    controller_idx: int,
    spell_name: str,
) -> list[str]:
    """Log when a cast spell matches a hidden or double agenda name."""
    player = game.players[controller_idx]
    details: list[str] = []
    if player.hidden_agenda_name and spell_name.lower() == player.hidden_agenda_name.lower():
        if player.hidden_agenda_revealed:
            details.append(f"hidden agenda matched {spell_name}")
    if player.double_agenda_names:
        first, second = player.double_agenda_names
        if spell_name.lower() in {first.lower(), second.lower()}:
            if player.hidden_agenda_revealed:
                details.append(f"double agenda matched {spell_name}")
    return details
