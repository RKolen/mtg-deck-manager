"""Keyword actions: Behold, Exert, Forage, Detain, Learn, Goad, Adapt, Reveal, Monstrosity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._token_factory import enter_token_from_blueprint
from engine.abilities.keywords.actions._parse import parse_amount_after_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.abilities.keywords.actions.detect import has_keyword_action
from engine.abilities.keywords.actions.targets import find_creature_by_uid
from engine.abilities.keywords.actions.library import manifest_top_of_library, seek_card
from engine.abilities.keywords.actions.tokens import create_creature_token_from_oracle
from engine.abilities.keywords.registry import has_registered_keyword
from engine.cards.oracle_parse import TokenBlueprint, parse_damage, parse_token_blueprint
from engine.core.game_object import CardObject
from engine.core.library_reveal import resolve_top_card_contest
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
    return resolve_top_card_contest(zones, prefix='clash')


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


def has_double(oracle_text: str | None) -> bool:
    """Return True when oracle uses Double as a keyword action."""
    return has_keyword_action(oracle_text, 'Double')


def has_assemble(oracle_text: str | None) -> bool:
    """Return True when oracle uses Assemble as a keyword action."""
    return has_keyword_action(oracle_text, 'Assemble')


def has_abandon(oracle_text: str | None) -> bool:
    """Return True when oracle uses Abandon as a keyword action."""
    return has_keyword_action(oracle_text, 'Abandon')


def has_open_attraction(oracle_text: str | None) -> bool:
    """Return True when oracle opens an Attraction."""
    return has_registered_keyword(oracle_text, 'Open an Attraction')


def has_meld(oracle_text: str | None) -> bool:
    """Return True when oracle uses Meld as a keyword action."""
    return has_keyword_action(oracle_text, 'Meld')


def apply_double_damage(
    game: GameState,
    controller_idx: int,
    oracle_text: str,
) -> str | None:
    """Double: deal damage twice (simplified)."""
    damage = parse_damage(oracle_text)
    if damage <= 0:
        return None
    opponent = 1 - controller_idx
    game.players[opponent].life -= damage * 2
    game.mark_player_was_dealt_damage(opponent)
    return f"double dealt {damage * 2} to P{opponent + 1}"


def open_attraction(game: GameState, controller_idx: int) -> str:
    """Open an Attraction: advance the attractions counter."""
    game.players[controller_idx].attractions += 1
    count = game.players[controller_idx].attractions
    return f"opened Attraction #{count}"


def assemble_legion(zones: ZoneManager, controller_idx: int) -> str:
    """Assemble: create a 2/2 Knight token."""
    blueprint = TokenBlueprint(
        name='Knight',
        type_line='Creature — Knight',
        power='2',
        toughness='2',
        oracle_text='',
    )
    name = enter_token_from_blueprint(zones, controller_idx, blueprint, cause='assemble')
    return f"assembled {name}"


def abandon_hand(zones: ZoneManager, controller_idx: int) -> str:
    """Abandon: discard two cards from hand."""
    hand = zones.player_zones[controller_idx].hand
    discarded = 0
    while hand and discarded < 2:
        card = hand.pop()
        if isinstance(card, CardObject):
            zones.player_zones[controller_idx].graveyard.append(card)
            discarded += 1
    return f"abandoned {discarded} card(s)"


def meld_permanents(zones: ZoneManager, top_uid: str | None, bottom_uid: str | None) -> str | None:
    """Meld: log melding two permanents (simplified)."""
    if top_uid is None or bottom_uid is None:
        return None
    try:
        top = zones.find_permanent(int(top_uid))
        bottom = zones.find_permanent(int(bottom_uid))
    except ValueError:
        return None
    if top is None or bottom is None:
        return None
    return f"melded {top.name} with {bottom.name}"


def detain_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Detain a creature: tap it and it won't untap during its controller's next untap."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['detained'] = 1
    target.tapped = True
    return f"detained {target.name}"


def has_blight(oracle_text: str | None) -> bool:
    """Return True when oracle uses Blight as a keyword action."""
    return has_keyword_action(oracle_text, 'Blight')


def blight_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Put a blight counter on a creature."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['blight'] = int(target.counters.get('blight', 0)) + 1
    return f"blighted {target.name}"


def has_cloak(oracle_text: str | None) -> bool:
    """Return True when oracle uses Cloak as a keyword action."""
    return has_keyword_action(oracle_text, 'Cloak')


def cloak_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Cloak: turn a creature face down (simplified)."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.face_down = True
    return f"cloaked {target.name}"


def has_heist(oracle_text: str | None) -> bool:
    """Return True when oracle uses Heist as a keyword action."""
    return has_keyword_action(oracle_text, 'Heist')


def heist_opponent_top(zones: ZoneManager, controller_idx: int) -> str:
    """Heist: exile the top card of an opponent's library."""
    opponent = 1 - controller_idx
    lib = zones.player_zones[opponent].library
    if not lib:
        return 'heist (empty library)'
    card = lib.pop(0)
    zones.player_zones[controller_idx].exile.append(card)
    name = card.card_info.name if isinstance(card, CardObject) and card.card_info else 'card'
    return f"heisted {name}"


def has_endure(oracle_text: str | None) -> bool:
    """Return True when oracle uses Endure as a keyword action."""
    return has_keyword_action(oracle_text, 'Endure')


def endure_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Endure: indestructible until end of turn (simplified counter)."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['endure'] = 1
    return f"{target.name} endures"


def has_harness(oracle_text: str | None) -> bool:
    """Return True when oracle uses Harness as a keyword action."""
    return has_keyword_action(oracle_text, 'Harness')


def harness_energy(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Harness: put an energy counter on a permanent."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['energy'] = int(target.counters.get('energy', 0)) + 1
    return f"harnessed energy on {target.name}"


def has_play(oracle_text: str | None) -> bool:
    """Return True when oracle uses Play as a keyword action."""
    return has_keyword_action(oracle_text, 'Play')


def play_top_card(zones: ZoneManager, controller_idx: int) -> str:
    """Play: put the top land from library onto the battlefield, else draw it."""
    lib = zones.player_zones[controller_idx].library
    if not lib:
        return 'played (empty library)'
    card = lib[0]
    if not isinstance(card, CardObject) or card.card_info is None:
        return 'played (unknown top card)'
    if card.card_info.is_land:
        zones.enter_battlefield(card, controller_idx, 'play', Zone.LIBRARY)
        return f"played {card.card_info.name}"
    drawn = zones.draw(controller_idx)
    name = drawn.card_info.name if isinstance(drawn, CardObject) and drawn.card_info else 'card'
    return f"played (drew {name})"


def has_set_in_motion(oracle_text: str | None) -> bool:
    """Return True when oracle uses Set in motion as a keyword action."""
    return has_keyword_action(oracle_text, 'Set in motion')


def set_in_motion(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Set in motion: put a time counter on a permanent."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['time'] = int(target.counters.get('time', 0)) + 1
    return f"set {target.name} in motion"


def has_cast_action(oracle_text: str | None) -> bool:
    """Return True when oracle uses Cast as a keyword action."""
    return has_keyword_action(oracle_text, 'Cast')


def cast_from_library(zones: ZoneManager, controller_idx: int) -> str:
    """Cast: manifest the top card of your library (simplified)."""
    perm = manifest_top_of_library(zones, controller_idx, cause='cast')
    if perm is None:
        return 'cast (empty library)'
    return f"cast {perm.name} from library"


def has_prepared(oracle_text: str | None) -> bool:
    """Return True when oracle uses Prepared as a keyword action."""
    return has_keyword_action(oracle_text, 'Prepared')


def prepared_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Prepared: mark a creature as prepared."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['prepared'] = 1
    return f"prepared {target.name}"


def has_time_travel(oracle_text: str | None) -> bool:
    """Return True when oracle uses Time Travel as a keyword action."""
    return has_keyword_action(oracle_text, 'Time Travel')


def time_travel(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Time Travel: put a lore counter on a permanent."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.counters['lore'] = int(target.counters.get('lore', 0)) + 1
    return f"time traveled {target.name}"


def has_plot_action(oracle_text: str | None) -> bool:
    """Return True when oracle uses Plot as a keyword action (not the plot mechanic)."""
    if not oracle_text:
        return False
    return has_keyword_action(oracle_text, 'Plot') and 'plot' in oracle_text.lower()


def plot_keyword_action() -> str:
    """Plot action: log plotting (simplified; setup uses casting.plot)."""
    return 'plotted (keyword action)'


def has_planeswalk(oracle_text: str | None) -> bool:
    """Return True when oracle uses Planeswalk as a keyword action."""
    return has_keyword_action(oracle_text, 'Planeswalk')


def planeswalk_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Planeswalk: add a loyalty counter on a planeswalker permanent."""
    if target_uid is None:
        return None
    try:
        perm = zones.find_permanent(int(target_uid))
    except ValueError:
        return None
    if perm is None or 'Planeswalker' not in perm.type_line:
        return None
    perm.counters['loyalty'] = int(perm.counters.get('loyalty', 0)) + 1
    return f"planeswalked {perm.name}"


def has_exchange(oracle_text: str | None) -> bool:
    """Return True when oracle uses Exchange as a keyword action."""
    return has_keyword_action(oracle_text, 'Exchange')


def exchange_library_tops(zones: ZoneManager, controller_idx: int) -> str:
    """Exchange: swap the top card of each player's library."""
    del controller_idx
    libs = [zones.player_zones[0].library, zones.player_zones[1].library]
    if not libs[0] or not libs[1]:
        return 'exchanged (empty library)'
    libs[0][0], libs[1][0] = libs[1][0], libs[0][0]
    return 'exchanged top of libraries'


def has_convert(oracle_text: str | None) -> bool:
    """Return True when oracle uses Convert as a keyword action."""
    return has_keyword_action(oracle_text, 'Convert')


def has_roll_attractions(oracle_text: str | None) -> bool:
    """Return True when oracle uses Roll to Visit Your Attractions."""
    return has_keyword_action(oracle_text, 'Roll to Visit Your Attractions')


def roll_attractions(game: GameState, controller_idx: int) -> str:
    """Roll to Visit Your Attractions: advance attractions counter."""
    game.players[controller_idx].attractions += 1
    count = game.players[controller_idx].attractions
    return f"rolled attractions (visit #{count})"


def has_earthbend(oracle_text: str | None) -> bool:
    """Return True when oracle uses Earthbend as a keyword action."""
    return has_keyword_action(oracle_text, 'Earthbend')


def has_airbend(oracle_text: str | None) -> bool:
    """Return True when oracle uses Airbend as a keyword action."""
    return has_keyword_action(oracle_text, 'Airbend')


def has_waterbend(oracle_text: str | None) -> bool:
    """Return True when oracle uses Waterbend as a keyword action."""
    return has_keyword_action(oracle_text, 'Waterbend')


def has_activate_action(oracle_text: str | None) -> bool:
    """Return True when oracle uses Activate as a keyword action."""
    return has_keyword_action(oracle_text, 'Activate')


def activate_keyword_action(
    zones: ZoneManager,
    target_uid: str | None,
) -> str | None:
    """Activate: tap a target permanent (simplified)."""
    if target_uid is None:
        return 'activated (no target)'
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        try:
            perm = zones.find_permanent(int(target_uid))
        except ValueError:
            return None
        if perm is None:
            return None
        perm.tapped = True
        return f"activated {perm.name}"
    target.tapped = True
    return f"activated {target.name}"


def bend_creature(
    zones: ZoneManager,
    target_uid: str | None,
    bend_name: str,
) -> str | None:
    """Put a bending counter on a creature."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    key = bend_name.lower()
    target.counters[key] = int(target.counters.get(key, 0)) + 1
    return f"{key} on {target.name}"
