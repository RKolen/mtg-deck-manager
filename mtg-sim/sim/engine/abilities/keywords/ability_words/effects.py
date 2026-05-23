"""Resolve ability-word triggered clauses (draw, damage, tokens)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.cards.oracle_parse import (
    parse_damage,
    parse_draw,
    parse_life_gain,
    parse_token_blueprint,
)
from engine.core.game_object import CardObject
from engine.abilities.keywords._token_factory import enter_token_from_blueprint
from engine.abilities.keywords.ability_words.clause import clause_after_ability_word
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import (
    ActivatedAbilityOnStack,
    Effect,
    GameObject,
    TriggeredAbilityOnStack,
)
if TYPE_CHECKING:
    from engine.core.game_state import GameState


def _permanent_from_stack_source(
    game: GameState,
    source: GameObject,
):
    """Return the source permanent for a triggered or activated ability on the stack."""
    if isinstance(source, (TriggeredAbilityOnStack, ActivatedAbilityOnStack)):
        return game.zones.find_permanent(source.source_permanent_id)
    return None


class AbilityWordEffect(Effect):
    """Apply a parsed oracle clause when an ability-word trigger resolves."""

    def __init__(self, clause: str) -> None:
        self.clause = clause

    def resolve(self, game: GameState, source: GameObject) -> str:
        """Draw, deal damage, gain life, or create a token from the clause."""
        permanent = _permanent_from_stack_source(game, source)
        if permanent is None:
            return ''
        controller = permanent.controller_idx
        parts: list[str] = []

        draw_count = parse_draw(self.clause)
        if draw_count > 0:
            drawn = []
            for _ in range(draw_count):
                card = game.zones.draw(controller)
                if card is not None:
                    drawn.append(card)
            parts.append(f"drew {len(drawn)} card(s)")

        damage = parse_damage(self.clause)
        if damage > 0:
            opponent = 1 - controller
            game.players[opponent].life -= damage
            game.mark_player_was_dealt_damage(opponent)
            parts.append(f"dealt {damage} damage")

        life = parse_life_gain(self.clause)
        if life > 0:
            game.gain_life(controller, life, source_permanent_id=permanent.obj_id)
            parts.append(f"gained {life} life")

        blueprint = parse_token_blueprint(self.clause)
        if blueprint is not None:
            name = enter_token_from_blueprint(
                game.zones,
                controller,
                blueprint,
                cause='ability_word',
            )
            parts.append(f"created {name}")

        return ', '.join(parts) if parts else 'triggered'

    def describe(self) -> str:
        """Return a short description for logs."""
        return f"Ability word: {self.clause[:40]}"


class ProwessEffect(Effect):
    """Put a +1/+1 counter on the source permanent (Monastery Swiftspear-style)."""

    def resolve(self, game: GameState, source: GameObject) -> str:
        """Apply one +1/+1 counter to the prowess source."""
        permanent = _permanent_from_stack_source(game, source)
        if permanent is None:
            return ''
        put_plus_counters(permanent, 1)
        return f"{permanent.name} gets +1/+1 from Prowess"

    def describe(self) -> str:
        """Return a short description for logs."""
        return "Prowess (+1/+1)"


class ValiantEffect(Effect):
    """Mark the source as having attacked with valiant this turn."""

    def resolve(self, game: GameState, source: GameObject) -> str:
        """Apply valiant clause and mark first attack used."""
        permanent = _permanent_from_stack_source(game, source)
        if permanent is None:
            return ''
        permanent.counters['valiant_this_turn'] = 1
        clause_effect = AbilityWordEffect(
            clause_after_ability_word(permanent.oracle_text, 'Valiant') or '',
        )
        detail = clause_effect.resolve(game, source)
        return detail or f"{permanent.name} valiant"

    def describe(self) -> str:
        """Return a short description for logs."""
        return 'Valiant'


class KinshipEffect(Effect):
    """Reveal the top card of your library; draw if it shares a creature type."""

    def resolve(self, game: GameState, source: GameObject) -> str:
        """Compare the top card's types to the kinship source."""
        permanent = _permanent_from_stack_source(game, source)
        if permanent is None:
            return ''
        library = game.zones.player_zones[permanent.controller_idx].library
        if not library:
            return 'kinship (empty library)'
        top = library[-1]
        if not isinstance(top, CardObject) or top.card_info is None:
            return 'kinship (no card)'
        source_types = {
            part.strip()
            for part in permanent.type_line.split('—')[0].split()
            if part.strip() not in ('Legendary', 'Creature', 'Artifact', 'Enchantment')
        }
        top_types = set(top.card_info.type_line.split('—')[0].split())
        if source_types & top_types:
            drawn = game.zones.draw(permanent.controller_idx)
            name = (
                drawn.card_info.name
                if drawn is not None and isinstance(drawn, CardObject) and drawn.card_info
                else 'card'
            )
            return f"kinship matched, drew {name}"
        return f"kinship revealed {top.card_info.name} (no match)"

    def describe(self) -> str:
        """Return a short description for logs."""
        return 'Kinship'


class ParleyEffect(Effect):
    """Each player reveals their top card; highest mana value draws (simplified)."""

    def resolve(self, game: GameState, source: GameObject) -> str:
        """Reveal tops, then the active player with the highest mana value draws."""
        permanent = _permanent_from_stack_source(game, source)
        if permanent is None:
            return ''
        scores: list[tuple[int, int, str]] = []
        for pidx in (0, 1):
            library = game.zones.player_zones[pidx].library
            if not library:
                scores.append((pidx, -1, ''))
                continue
            top = library[-1]
            if isinstance(top, CardObject) and top.card_info is not None:
                mv = int(top.card_info.cmc)
                name = top.card_info.name
            else:
                mv = 0
                name = 'card'
            scores.append((pidx, mv, name))
        winner_idx, best_mv, winner_card = max(scores, key=lambda item: item[1])
        if best_mv < 0:
            return 'parley (no libraries)'
        drawn = game.zones.draw(winner_idx)
        draw_name = (
            drawn.card_info.name
            if drawn is not None and isinstance(drawn, CardObject) and drawn.card_info
            else 'nothing'
        )
        return f"parley: P{winner_idx + 1} won with {winner_card} (MV {best_mv}), drew {draw_name}"

    def describe(self) -> str:
        """Return a short description for logs."""
        return "Parley"
