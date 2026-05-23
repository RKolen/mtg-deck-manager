"""Keyword actions: Behold, Exert, Forage, Detain, Learn, Goad, Adapt, Reveal, Monstrosity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._token_factory import enter_token_from_blueprint
from engine.abilities.keywords.actions._parse import parse_amount_after_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.abilities.keywords.actions.detect import has_keyword_action
from engine.abilities.keywords.actions.targets import find_creature_by_uid
from engine.abilities.keywords.actions.library import seek_card
from engine.abilities.keywords.actions.tokens import create_creature_token_from_oracle
from engine.abilities.keywords.registry import has_registered_keyword
from engine.cards.oracle_parse import TokenBlueprint, parse_token_blueprint
from engine.core.game_object import CardObject
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState
    from engine.core.zones import ZoneManager


def has_behold(oracle_text: str | None) -> bool:
    """Return True when oracle text includes Behold."""
    return has_registered_keyword(oracle_text, 'Behold')


def has_exert(oracle_text: str | None) -> bool:
    """Return True when oracle uses Exert as a keyword action."""
    return has_keyword_action(oracle_text, 'Exert')


def has_forage(oracle_text: str | None) -> bool:
    """Return True when oracle uses Forage as a keyword action."""
    return has_keyword_action(oracle_text, 'Forage')


def has_detain(oracle_text: str | None) -> bool:
    """Return True when oracle uses Detain as a keyword action."""
    return has_keyword_action(oracle_text, 'Detain')


def behold_top_card(zones: ZoneManager, controller_idx: int) -> str:
    """Reveal the top card of the library (simplified Behold)."""
    library = zones.player_zones[controller_idx].library
    if not library:
        return 'beheld (empty library)'
    top = library[-1]
    if isinstance(top, CardObject) and top.card_info is not None:
        name = top.card_info.name
        is_land = top.card_info.is_land
    else:
        name = 'unknown'
        is_land = False
    return f"beheld {name}" + (' (land)' if is_land else '')


def behold_draw_if_clause(oracle_text: str, zones: ZoneManager, controller_idx: int) -> str | None:
    """Draw a card when Behold is followed by a draw clause."""
    lowered = oracle_text.lower()
    if 'behold' not in lowered or 'draw' not in lowered:
        return None
    drawn = zones.draw(controller_idx)
    if drawn is None:
        return 'drew 0 (empty library)'
    name = drawn.card_info.name if isinstance(drawn, CardObject) and drawn.card_info else 'card'
    return f"drew {name}"


def exert_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Exert a target creature: tap it and skip its next untap step."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['exerted'] = 1
    target.tapped = True
    return f"exerted {target.name}"


def forage_cost(zones: ZoneManager, controller_idx: int, game: GameState | None) -> str | None:
    """Forage: exile three cards from your graveyard or sacrifice a Food."""
    graveyard = zones.player_zones[controller_idx].graveyard
    if len(graveyard) >= 3:
        for _ in range(3):
            graveyard.pop()
        return 'foraged (exiled 3 from graveyard)'
    for perm in list(zones.battlefield):
        if perm.controller_idx != controller_idx:
            continue
        if 'Food' not in perm.type_line:
            continue
        if game is None:
            return None
        zones.leave_battlefield(perm, Zone.GRAVEYARD, 'sacrifice', game)
        return f"foraged (sacrificed {perm.name})"
    return None


def has_learn(oracle_text: str | None) -> bool:
    """Return True when oracle uses Learn as a keyword action."""
    return has_keyword_action(oracle_text, 'Learn')


def has_goad(oracle_text: str | None) -> bool:
    """Return True when oracle uses Goad as a keyword action."""
    return has_keyword_action(oracle_text, 'Goad')


def has_adapt(oracle_text: str | None) -> bool:
    """Return True when oracle uses Adapt as a keyword action."""
    return has_keyword_action(oracle_text, 'Adapt')


def has_reveal(oracle_text: str | None) -> bool:
    """Return True when oracle uses Reveal as a keyword action."""
    return has_keyword_action(oracle_text, 'Reveal')


def has_monstrosity(oracle_text: str | None) -> bool:
    """Return True when oracle uses Monstrosity as a keyword action."""
    return has_keyword_action(oracle_text, 'Monstrosity')


def learn_draw(zones: ZoneManager, controller_idx: int) -> str:
    """Learn: draw a card (lesson-from-sideboard omitted)."""
    drawn = zones.draw(controller_idx)
    if drawn is None:
        return 'learned (empty library)'
    name = drawn.card_info.name if isinstance(drawn, CardObject) and drawn.card_info else 'card'
    return f"learned ({name})"


def goad_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Goad a creature (simplified: mark goaded)."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['goaded'] = 1
    return f"goaded {target.name}"


def adapt_creature(zones: ZoneManager, target_uid: str | None, oracle_text: str) -> str | None:
    """Adapt: put +1/+1 counters if the creature has none from adapt yet."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    if target.counters.get('adapted'):
        return None
    amount = parse_amount_after_keyword(oracle_text, 'adapt')
    put_plus_counters(target, amount)
    target.counters['adapted'] = 1
    return f"adapted {target.name} (+{amount}/+{amount})"


def reveal_top_card(zones: ZoneManager, controller_idx: int) -> str:
    """Reveal the top card of a library."""
    return behold_top_card(zones, controller_idx).replace('beheld', 'revealed', 1)


def monstrosity_creature(
    zones: ZoneManager,
    target_uid: str | None,
    oracle_text: str,
) -> str | None:
    """Monstrosity: put X +1/+1 counters if not already monstrous."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    if target.counters.get('monstrous'):
        return None
    amount = parse_amount_after_keyword(oracle_text, 'monstrosity')
    put_plus_counters(target, amount)
    target.counters['monstrous'] = 1
    return f"{target.name} became monstrous (+{amount}/+{amount})"


def has_suspect(oracle_text: str | None) -> bool:
    """Return True when oracle uses Suspect as a keyword action."""
    return has_keyword_action(oracle_text, 'Suspect')


def has_incubate(oracle_text: str | None) -> bool:
    """Return True when oracle uses Incubate as a keyword action."""
    return has_keyword_action(oracle_text, 'Incubate')


def has_clash(oracle_text: str | None) -> bool:
    """Return True when oracle uses Clash as a keyword action."""
    return has_keyword_action(oracle_text, 'Clash')


def has_collect_evidence(oracle_text: str | None) -> bool:
    """Return True when oracle uses Collect evidence as a keyword action."""
    return has_registered_keyword(oracle_text, 'Collect evidence')


def has_discard_action(oracle_text: str | None) -> bool:
    """Return True when oracle uses Discard as a keyword action."""
    return has_keyword_action(oracle_text, 'Discard')


def has_venture(oracle_text: str | None) -> bool:
    """Return True when oracle uses Venture into the dungeon."""
    return has_registered_keyword(oracle_text, 'Venture into the dungeon')


def suspect_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Mark a creature suspect (simplified)."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['suspect'] = 1
    return f"suspected {target.name}"


def incubate(zones: ZoneManager, controller_idx: int, oracle_text: str) -> str:
    """Create an incubator token with +1/+1 counters (simplified)."""
    amount = parse_amount_after_keyword(oracle_text, 'incubate')
    blueprint = TokenBlueprint(
        name='Incubator',
        type_line='Artifact — Phyrexian Incubator',
        power='0',
        toughness='0',
        oracle_text='',
    )
    enter_token_from_blueprint(zones, controller_idx, blueprint, cause='incubate')
    for perm in reversed(zones.battlefield):
        if perm.controller_idx == controller_idx and 'Incubator' in perm.type_line:
            put_plus_counters(perm, amount)
            break
    return f"incubated ({amount} counter(s))"


def clash(zones: ZoneManager) -> str:
    """Each player reveals their top card; highest mana value wins a draw."""
    scores: list[tuple[int, int, str]] = []
    for pidx in (0, 1):
        library = zones.player_zones[pidx].library
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
        return 'clash (no libraries)'
    drawn = zones.draw(winner_idx)
    draw_name = (
        drawn.card_info.name
        if drawn is not None and isinstance(drawn, CardObject) and drawn.card_info
        else 'nothing'
    )
    return f"clash: P{winner_idx + 1} won with {winner_card} (MV {best_mv}), drew {draw_name}"


def collect_evidence(zones: ZoneManager, controller_idx: int) -> str | None:
    """Collect evidence when six or more cards are in your graveyard."""
    if len(zones.player_zones[controller_idx].graveyard) < 6:
        return None
    return 'collected evidence (6+ cards in graveyard)'


def discard_from_hand(zones: ZoneManager, controller_idx: int) -> str:
    """Discard the last card from hand (simplified Discard action)."""
    hand = zones.player_zones[controller_idx].hand
    if not hand:
        return 'discarded (empty hand)'
    card = hand.pop()
    assert isinstance(card, CardObject)
    zones.player_zones[controller_idx].graveyard.append(card)
    name = card.card_info.name if card.card_info else 'card'
    return f"discarded {name}"


def venture_into_dungeon(game: GameState, controller_idx: int) -> str:
    """Advance the dungeon room counter (simplified)."""
    player = game.players[controller_idx]
    player.dungeon_room += 1
    return f"ventured to dungeon room {player.dungeon_room}"


def has_conjure(oracle_text: str | None) -> bool:
    """Return True when oracle uses Conjure as a keyword action."""
    return has_keyword_action(oracle_text, 'Conjure')


def has_transform(oracle_text: str | None) -> bool:
    """Return True when oracle uses Transform as a keyword action."""
    return has_keyword_action(oracle_text, 'Transform')


def has_attach(oracle_text: str | None) -> bool:
    """Return True when oracle uses Attach as a keyword action."""
    return has_keyword_action(oracle_text, 'Attach')


def has_vote(oracle_text: str | None) -> bool:
    """Return True when oracle uses Vote as a keyword action."""
    return has_keyword_action(oracle_text, 'Vote')


def has_role_token(oracle_text: str | None) -> bool:
    """Return True when oracle uses Role token as a keyword action."""
    return has_registered_keyword(oracle_text, 'Role token')


def conjure_to_hand(zones: ZoneManager, controller_idx: int, oracle_text: str) -> str:
    """Conjure: put a card into hand (simplified as seek/draw)."""
    sought = seek_card(zones, controller_idx, oracle_text)
    if sought is not None:
        zones.player_zones[controller_idx].hand.append(sought)
        name = sought.card_info.name if sought.card_info else 'card'
        return f"conjured {name}"
    drawn = zones.draw(controller_idx)
    if drawn is None:
        return 'conjured (empty library)'
    name = drawn.card_info.name if isinstance(drawn, CardObject) and drawn.card_info else 'card'
    return f"conjured {name}"


def transform_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Transform: toggle face-down state (simplified)."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.face_down = not target.face_down
    state = 'face-down' if target.face_down else 'face-up'
    return f"{target.name} transformed ({state})"


def attach_to_creature(
    zones: ZoneManager,
    equipment_uid: str | None,
    host_uid: str | None,
) -> str | None:
    """Attach an aura or equipment to a host creature."""
    if equipment_uid is None or host_uid is None:
        return None
    try:
        equipment = zones.find_permanent(int(equipment_uid))
        host = zones.find_permanent(int(host_uid))
    except ValueError:
        return None
    if equipment is None or host is None:
        return None
    if 'Creature' not in host.type_line:
        return None
    equipment.attached_to = host.obj_id
    return f"{equipment.name} attached to {host.name}"


def resolve_vote(oracle_text: str) -> str:
    """Vote: log a simplified council outcome (controller wins)."""
    del oracle_text
    return 'vote resolved (controller wins)'


def create_role_token(zones: ZoneManager, controller_idx: int, oracle_text: str) -> str | None:
    """Create a Role token from oracle text."""
    blueprint = parse_token_blueprint(oracle_text)
    if blueprint is None:
        created = create_creature_token_from_oracle(zones, controller_idx, oracle_text)
        return f"created role {created}" if created else None
    enter_token_from_blueprint(zones, controller_idx, blueprint, cause='role')
    return f"created {blueprint.name}"


def detain_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Detain a creature: tap it and it won't untap during its controller's next untap."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['detained'] = 1
    target.tapped = True
    return f"detained {target.name}"
